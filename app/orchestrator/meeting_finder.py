"""Meeting finder module - handles finding meetings from database and Google Calendar."""

from typing import Optional, Dict, Any, Tuple
from datetime import datetime, timezone, timedelta, date
from sqlalchemy.orm import Session
from app.memory.repo import MemoryRepository
from app.integrations.google_calendar_client import (
    get_calendar_event_by_id,
    get_calendar_events_on_date,
    get_calendar_events_by_time_range,
    search_calendar_events_by_keyword
)
from app.memory.schemas import MeetingOption
from app.utils.date_utils import extract_event_datetime
from app.utils.calendar_utils import sort_events_by_date


class MeetingFinder:
    """Handles finding meetings from database and Google Calendar."""
    
    def __init__(self, db: Session, memory: MemoryRepository):
        self.db = db
        self.memory = memory
    
    def find_meeting_in_database(
        self,
        meeting_id: Optional[int] = None,
        client_id: Optional[int] = None,
        user_id: Optional[int] = None,
        client_name: Optional[str] = None,
        target_date: Optional[datetime] = None
    ) -> Optional[int]:
        """
        Find a meeting in the database.
        Returns meeting_id if found, None otherwise.
        """
        try:
            from datetime import datetime, timezone
            
            print(f"      [MeetingFinder] find_meeting_in_database called")
            print(f"         meeting_id={meeting_id}, client_id={client_id}, user_id={user_id}, client_name={client_name}, target_date={target_date}")
            
            # If meeting_id is provided, verify it exists
            if meeting_id:
                print(f"         ✅ meeting_id provided, verifying existence...")
                db_meeting = self.memory.get_meeting_by_id(meeting_id)
                if db_meeting:
                    print(f"         ✅ Meeting {meeting_id} found: {db_meeting.title}")
                    return meeting_id
                print(f"         ❌ Meeting {meeting_id} not found")
                return None
            
            now = datetime.utcnow()
            if now.tzinfo is None:
                now_aware = now.replace(tzinfo=timezone.utc)
            else:
                now_aware = now
            
            target_date_only = target_date.date() if target_date else None
            
            # Search by client name first
            if client_name and user_id:
                print(f"         🔍 Searching by client_name='{client_name}' for user_id={user_id}...")
                clients = self.memory.search_clients_by_name(client_name, user_id=user_id)
                print(f"         Found {len(clients)} matching client(s)")
                if clients:
                    client_id = clients[0].id
                    print(f"         Using client_id={client_id} ({clients[0].name})")
                    meetings = self.memory.get_meetings_by_client(client_id, limit=50)
                    print(f"         Found {len(meetings)} meetings for this client")
                    past_meetings = self._filter_past_meetings(meetings, now_aware)
                    print(f"         Filtered to {len(past_meetings)} past meetings")
                    if past_meetings:
                        if target_date_only:
                            date_matched = [
                                m for m in past_meetings
                                if m.scheduled_time and m.scheduled_time.date() == target_date_only
                            ]
                            if date_matched:
                                print(f"         ✅ Returning date-matched meeting: {date_matched[0].id} - {date_matched[0].title}")
                                return date_matched[0].id
                            else:
                                print(f"         ❌ No past meetings found for client on target_date={target_date_only}")
                                return None
                        print(f"         ✅ Returning most recent: {past_meetings[0].id} - {past_meetings[0].title}")
                        return past_meetings[0].id
                    else:
                        print(f"         ❌ No past meetings found for client")
                else:
                    print(f"         ❌ No clients found matching '{client_name}'")
                # If client_name was provided but no meeting found, do not fall back to user-level search
                return None
            
            # Search by client_id
            if client_id:
                print(f"         🔍 Searching by client_id={client_id}...")
                meetings = self.memory.get_meetings_by_client(client_id, limit=50)
                print(f"         Found {len(meetings)} meetings")
                past_meetings = self._filter_past_meetings(meetings, now_aware)
                print(f"         Filtered to {len(past_meetings)} past meetings")
                if past_meetings:
                    if target_date_only:
                        date_matched = [
                            m for m in past_meetings
                            if m.scheduled_time and m.scheduled_time.date() == target_date_only
                        ]
                        if date_matched:
                            print(f"         ✅ Returning date-matched meeting: {date_matched[0].id} - {date_matched[0].title}")
                            return date_matched[0].id
                        else:
                            print(f"         ❌ No past meetings found for client on target_date={target_date_only}")
                            return None
                    print(f"         ✅ Returning most recent: {past_meetings[0].id} - {past_meetings[0].title}")
                    return past_meetings[0].id
                # If client_id was provided but no meeting found, do not fall back to user-level search
                return None
            
            # Search by user_id
            if user_id and not client_name and not client_id:
                print(f"         🔍 Searching by user_id={user_id}...")
                meetings = self.memory.get_meetings_by_user(user_id, limit=50)
                print(f"         Found {len(meetings)} meetings")
                past_meetings = self._filter_past_meetings(meetings, now_aware)
                print(f"         Filtered to {len(past_meetings)} past meetings")
                if past_meetings:
                    print(f"         ✅ Returning most recent: {past_meetings[0].id} - {past_meetings[0].title}")
                    return past_meetings[0].id
            
            print(f"         ❌ No meeting found in database")
            return None
        except Exception as e:
            import traceback
            print(f"         ❌ ERROR in find_meeting_in_database: {str(e)}")
            print(f"         📋 Traceback: {traceback.format_exc()}")
            return None
    
    def _filter_past_meetings(self, meetings, now_aware):
        """Filter and sort past meetings."""
        from datetime import datetime, timezone
        
        past_meetings = []
        for m in meetings:
            if m.scheduled_time:
                meeting_time = m.scheduled_time
                if meeting_time.tzinfo is None:
                    meeting_time = meeting_time.replace(tzinfo=timezone.utc)
                if meeting_time < now_aware:
                    past_meetings.append(m)
        
        if past_meetings:
            def get_sort_key(m):
                if not m.scheduled_time:
                    return datetime.min.replace(tzinfo=timezone.utc) if now_aware.tzinfo else datetime.min
                dt = m.scheduled_time
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt
            
            past_meetings.sort(key=get_sort_key, reverse=True)
        
        return past_meetings
    
    def find_meeting_in_calendar(
        self,
        client_name: Optional[str] = None,
        target_date: Optional[datetime] = None,
        selected_meeting_number: Optional[int] = None,
        calendar_event_id: Optional[str] = None,
        user_id: Optional[int] = None
    ) -> Tuple[Optional[Dict[str, Any]], Optional[list]]:
        """
        Find a meeting in Google Calendar.
        Returns (calendar_event, meeting_options) tuple.
        If meeting_options is not None, user needs to select.
        """
        print(f"      [MeetingFinder] find_meeting_in_calendar called")
        print(f"         client_name={client_name}, target_date={target_date}, selected_meeting_number={selected_meeting_number}, calendar_event_id={calendar_event_id}, user_id={user_id}")
        
        from datetime import datetime, timedelta, timezone
        from app.integrations.google_calendar_client import _is_event_in_past
        
        common_words = {'summarize', 'meeting', 'last', 'my', 'the', 'a', 'an', 'for', 'with', 'prepare', 'brief'}
        
        try:
            # PRIORITY 1: If calendar_event_id is provided, fetch it directly
            if calendar_event_id:
                print(f"         🔍 PRIORITY 1: Fetching calendar event directly by ID: {calendar_event_id}")
                try:
                    event = get_calendar_event_by_id(calendar_event_id)
                    if event:
                        print(f"         ✅ Successfully fetched calendar event: {event.get('summary', 'Untitled')}")
                        return event, None
                    else:
                        print(f"         ⚠️ Calendar event {calendar_event_id} not found")
                except Exception as e:
                    print(f"         ❌ Error fetching calendar event by ID: {e}")
                    # Fall through to search if direct fetch fails
            # Search by client name if provided
            if client_name and client_name.lower() not in common_words:
                print(f"         🔍 PRIORITY 2: Searching by client_name='{client_name}'...")
                
                # If target_date is provided, use exact date search
                if target_date:
                    target_date_only = target_date.date()
                    print(f"         📅 EXACT DATE MODE: Target date provided: {target_date_only}")
                    print(f"         🔍 Fetching ALL events on EXACT date: {target_date_only}")
                    
                    # Get ALL events on that exact date
                    events_on_date = get_calendar_events_on_date(target_date_only)
                    print(f"         ✅ Found {len(events_on_date)} total events on {target_date_only}")
                    
                    # Filter by client name (keyword)
                    client_name_lower = client_name.lower()
                    matching_events = [
                        evt for evt in events_on_date
                        if client_name_lower in evt.get('summary', '').lower()
                        or client_name_lower in evt.get('description', '').lower()
                        or client_name_lower in evt.get('location', '').lower()
                    ]
                    
                    print(f"         ✅ Found {len(matching_events)} events matching client '{client_name}' on {target_date_only}")
                    
                    # Filter to past events only (in case target_date is today)
                    now = datetime.now(timezone.utc)
                    matching_events = [evt for evt in matching_events if _is_event_in_past(evt, now)]
                    
                    if not matching_events:
                        print(f"         ❌ No events found matching client '{client_name}' on {target_date_only}")
                        # Before falling back, try searching within date window
                        print(f"         🔍 Attempting date window search as fallback...")
                        window_events = self._search_events_within_date_window(
                            client_name=client_name,
                            target_date=target_date_only,
                            window_days=3
                        )
                        
                        # Filter window events to past events only
                        if window_events:
                            window_events = [evt for evt in window_events if _is_event_in_past(evt, now)]
                        
                        if window_events:
                            print(f"         ✅ Found {len(window_events)} event(s) in date window, using as fallback")
                            # ALWAYS return options for user selection (even if only one match)
                            print(f"         📋 Returning options for user selection")
                            return None, self._create_meeting_options(window_events, client_name, user_id)
                        else:
                            print(f"         ❌ No events found in date window either")
                            return None, None
                    
                    # ALWAYS return options for user selection (even if only one match)
                    # This allows user to confirm before we fetch transcript
                    print(f"         📋 Found {len(matching_events)} event(s), returning options for user selection")
                    return None, self._create_meeting_options(matching_events, client_name, user_id)
                else:
                    # No target date - search recent past (last 90 days)
                    search_days_back = 90
                    print(f"         📅 No target date, searching last {search_days_back} days")
                    matching_events = search_calendar_events_by_keyword(
                        client_name,
                        max_results=50,
                        include_past=True,
                        include_future=False,
                        days_back=search_days_back,
                        past_only=True
                    )
                    print(f"         Found {len(matching_events)} matching events")
                    
                    # No date provided - prioritize by client name in title
                    if matching_events:
                        client_name_lower = client_name.lower()
                        priority_with_client = []
                        priority_other = []
                        
                        for evt in matching_events:
                            evt_title = evt.get('summary', '').lower()
                            if client_name_lower in evt_title:
                                priority_with_client.append(evt)
                            else:
                                priority_other.append(evt)
                        
                        # When client name is specified, prefer events with client in title
                        if priority_with_client:
                            matching_events = priority_with_client
                            print(f"         ✅ Using only {len(priority_with_client)} events with client in title (filtered out {len(priority_other)} others)")
                        else:
                            matching_events = priority_with_client + priority_other
                            print(f"         ⚠️ No events with client in title, using all {len(matching_events)} matches")
                    
                    matching_events = self._sort_events_by_date(matching_events)
                    print(f"         Sorted events (showing first {min(10, len(matching_events))}):")
                    for i, evt in enumerate(matching_events[:10], 1):
                        evt_date = evt.get('start', {}).get('dateTime', evt.get('start', {}).get('date', 'No date'))
                        date_display = evt_date[:10] if len(evt_date) >= 10 else evt_date
                        print(f"            {i}. {evt.get('summary', 'Untitled')} - {date_display}")
                    
                    # Handle selection by number (user has already selected)
                    if selected_meeting_number:
                        print(f"         🔍 User selected meeting number: {selected_meeting_number}")
                        meeting_index = selected_meeting_number - 1
                        if 0 <= meeting_index < len(matching_events):
                            selected_event = matching_events[meeting_index]
                            print(f"         ✅ Selected event: '{selected_event.get('summary', 'Untitled')}'")
                            return selected_event, None
                        else:
                            print(f"         ❌ Meeting number {selected_meeting_number} out of range (max: {len(matching_events)})")
                            return None, None
                    
                    # Handle selection by calendar_event_id (user has already selected)
                    if calendar_event_id:
                        try:
                            event = get_calendar_event_by_id(calendar_event_id)
                            if event:
                                print(f"         ✅ Found event by ID: '{event.get('summary', 'Untitled')}'")
                                return event, None
                        except Exception as e:
                            print(f"         ⚠️ Error fetching event by ID: {str(e)}")
                        selected_event = next((e for e in matching_events if e.get('id') == calendar_event_id), None)
                        if selected_event:
                            print(f"         ✅ Found event in matching list: '{selected_event.get('summary', 'Untitled')}'")
                            return selected_event, None
                    
                    # ALWAYS return options for user selection when client_name is provided
                    # This allows user to confirm before we fetch transcript
                    if matching_events:
                        print(f"         📋 Returning {len(matching_events)} meeting option(s) for user selection")
                        return None, self._create_meeting_options(matching_events, client_name, user_id)
                    else:
                        print(f"         ❌ No matching events found")
                        return None, None
            
            # No client name - get recent past events
            else:
                print(f"         🔍 PRIORITY 3: No client_name, getting recent past events...")
                end_time = datetime.utcnow()
                start_time = end_time - timedelta(days=90)
                past_events = get_calendar_events_by_time_range(start_time, end_time)
                print(f"         Found {len(past_events)} events in time range")
                
                if past_events:
                    now = datetime.utcnow()
                    past_only_events = [e for e in past_events if _is_event_in_past(e, now)]
                    print(f"         Filtered to {len(past_only_events)} past events")
                    
                    if past_only_events:
                        past_only_events = self._sort_events_by_date(past_only_events)
                        print(f"         Sorted events (showing first 3):")
                        for i, evt in enumerate(past_only_events[:3], 1):
                            print(f"            {i}. {evt.get('summary', 'Untitled')} - {evt.get('start', {}).get('dateTime', 'No date')[:10]}")
                        
                        # Handle selection by number
                        if selected_meeting_number:
                            print(f"         🔍 User selected meeting number: {selected_meeting_number}")
                            meeting_index = selected_meeting_number - 1
                            if 0 <= meeting_index < len(past_only_events):
                                selected_event = past_only_events[meeting_index]
                                print(f"         ✅ Selected event: {selected_event.get('summary', 'Untitled')}")
                                return selected_event, None
                            else:
                                print(f"         ❌ Meeting number {selected_meeting_number} out of range (max: {len(past_only_events)})")
                                return None, None
                        
                        # Handle selection by calendar_event_id (if not already handled above)
                        if calendar_event_id:
                            # Try direct fetch first
                            try:
                                event = get_calendar_event_by_id(calendar_event_id)
                                if event:
                                    return event, None
                            except:
                                pass
                            # Fallback to search in past events
                            selected_event = next((e for e in past_only_events if e.get('id') == calendar_event_id), None)
                            if selected_event:
                                return selected_event, None
                        
                        # Automatically select the most recent event (first after sorting)
                        if past_only_events:
                            selected_event = past_only_events[0]
                            print(f"         ✅ Auto-selected most recent event: '{selected_event.get('summary', 'Untitled')}'")
                            if len(past_only_events) > 1:
                                print(f"         ℹ️ Found {len(past_only_events)} past events, using the most recent")
                            return selected_event, None
                        else:
                            print(f"         ❌ No past events found")
                            return None, None
        
        except Exception as e:
            import traceback
            print(f"         ❌ ERROR in find_meeting_in_calendar: {str(e)}")
            print(f"         📋 Traceback: {traceback.format_exc()}")
            return None, None
    
    # REMOVED: _is_event_date_within_range - no longer used
    # We now use exact date matching via get_events_on_date() which only returns events on the exact date
    # def _is_event_date_within_range(self, event: Dict[str, Any], target_date: datetime, tolerance: timedelta) -> bool:
    #     """Check if an event's date is within tolerance of target_date."""
    #     # ... (removed fuzzy matching logic)
    
    def _is_event_on_exact_date(self, event: Dict[str, Any], target_date: date) -> bool:
        """Check if an event is on the exact target date (same day, no tolerance)."""
        try:
            evt_dt = extract_event_datetime(event)
            if not evt_dt:
                return False
            
            # Compare just the date part (ignore time)
            return evt_dt.date() == target_date
        except (ValueError, AttributeError, TypeError):
            return False
    
    def _search_events_within_date_window(
        self,
        client_name: str,
        target_date: date,
        window_days: int = 3
    ) -> list:
        """
        Search for calendar events within a date window around target_date.
        
        Args:
            client_name: Client name to search for (case-insensitive)
            target_date: Target date to search around
            window_days: Number of days before/after target_date to search (default: 3)
        
        Returns:
            List of matching calendar events sorted newest → oldest
        """
        from datetime import datetime, timezone
        
        # Build date range: (target_date - window_days) → (target_date + window_days)
        start_date = target_date - timedelta(days=window_days)
        end_date = target_date + timedelta(days=window_days)
        
        # Convert to datetime for get_calendar_events_by_time_range
        # Start at beginning of start_date
        start_dt = datetime.combine(start_date, datetime.min.time()).replace(tzinfo=timezone.utc)
        # End at end of end_date
        end_dt = datetime.combine(end_date, datetime.max.time()).replace(tzinfo=timezone.utc)
        
        print(f"         🔍 Searching date window: {start_date} to {end_date} (±{window_days} days)")
        
        # Fetch ALL calendar events in the date range
        all_events = get_calendar_events_by_time_range(start_dt, end_dt)
        print(f"         ✅ Found {len(all_events)} total events in date window")
        
        # Filter events where summary/description/location contain client_name (case-insensitive)
        client_name_lower = client_name.lower()
        matching_events = [
            evt for evt in all_events
            if client_name_lower in evt.get('summary', '').lower()
            or client_name_lower in evt.get('description', '').lower()
            or client_name_lower in evt.get('location', '').lower()
        ]
        
        print(f"         ✅ Found {len(matching_events)} events matching client '{client_name}' in date window")
        
        # Sort results newest → oldest using existing sort helper
        if matching_events:
            matching_events = self._sort_events_by_date(matching_events)
        
        return matching_events
    
    def _sort_events_by_date(self, events):
        """Sort events by date (most recent first)."""
        return sort_events_by_date(events, reverse=True)
    
    def _create_meeting_options(self, events, client_name: Optional[str], user_id: Optional[int]) -> list:
        """Create MeetingOption objects from calendar events."""
        from app.memory.schemas import MeetingOption
        
        meeting_options = []
        for i, evt in enumerate(events, 1):
            evt_title = evt.get('summary', 'Untitled')
            evt_date = (evt.get('start', {}).get('dateTime') or 
                       evt.get('start', {}).get('date', 'Unknown'))
            date_display = evt_date[:10] if len(evt_date) >= 10 else evt_date
            
            evt_id = evt.get('id')
            db_meeting_id = None
            if evt_id:
                db_meeting = self.memory.get_meeting_by_calendar_event_id(evt_id)
                if db_meeting:
                    db_meeting_id = db_meeting.id
            
            meeting_options.append(MeetingOption(
                id=f"calendar_{evt_id}" if evt_id else f"event_{i}",
                title=evt_title,
                date=date_display,
                calendar_event_id=evt_id,
                meeting_id=db_meeting_id,
                client_name=client_name
            ))
        
        return meeting_options

