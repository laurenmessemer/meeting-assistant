"""Google Calendar client."""

from datetime import datetime, timedelta, timezone, date
from typing import List, Dict, Any, Optional
from googleapiclient.discovery import build
from app.integrations.google_auth import get_google_credentials
from app.utils.date_utils import extract_event_datetime


def _is_event_in_past(event: Dict[str, Any], now: datetime) -> bool:
    """Check if a calendar event has already occurred."""
    event_time = extract_event_datetime(event)
    
    if not event_time:
        return False
    
    # Ensure now has timezone for comparison
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    
    # event_time is already in UTC from extract_event_datetime
    return event_time < now


class GoogleCalendarClient:
    """Client for interacting with Google Calendar API."""
    
    def __init__(self):
        creds = get_google_credentials()
        self.service = build('calendar', 'v3', credentials=creds)
    
    def get_upcoming_events(self, max_results: int = 10, time_min: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """
        Get upcoming calendar events.
        
        Args:
            max_results: Maximum number of events to return
            time_min: Start time for events (defaults to now)
        
        Returns:
            List of event dictionaries
        """
        if time_min is None:
            time_min = datetime.utcnow()
        
        try:
            events_result = self.service.events().list(
                calendarId='primary',
                timeMin=time_min.isoformat() + 'Z',
                maxResults=max_results,
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            
            events = events_result.get('items', [])
            return events
        except Exception as e:
            raise Exception(f"Error fetching calendar events: {str(e)}")
    
    def get_event_by_id(self, event_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a specific calendar event by ID.
        
        Args:
            event_id: Google Calendar event ID
        
        Returns:
            Event dictionary or None if not found
        """
        try:
            event = self.service.events().get(
                calendarId='primary',
                eventId=event_id
            ).execute()
            return event
        except Exception as e:
            raise Exception(f"Error fetching event: {str(e)}")
    
    def get_events_on_date(self, target_date: date) -> List[Dict[str, Any]]:
        """
        Return ALL Google Calendar events that occur on the exact target_date.
        This ensures we only pull events for one day, not an entire month or range.
        
        Args:
            target_date: The date to search for events (date object)
        
        Returns:
            List of event dictionaries that occur on that exact date
        """
        start_dt = datetime.combine(target_date, datetime.min.time()).replace(tzinfo=timezone.utc)
        end_dt = datetime.combine(target_date, datetime.max.time()).replace(tzinfo=timezone.utc)
        
        events = self.get_events_by_time_range(start_dt, end_dt)
        return events
    
    def get_events_by_time_range(
        self, 
        start_time: datetime, 
        end_time: datetime
    ) -> List[Dict[str, Any]]:
        """
        Get events within a specific time range.
        
        Args:
            start_time: Start of time range
            end_time: End of time range
        
        Returns:
            List of event dictionaries
        """
        try:
            events_result = self.service.events().list(
                calendarId='primary',
                timeMin=start_time.isoformat() + 'Z',
                timeMax=end_time.isoformat() + 'Z',
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            
            events = events_result.get('items', [])
            return events
        except Exception as e:
            raise Exception(f"Error fetching calendar events: {str(e)}")
    
    def get_event_attendees(self, event_id: str) -> List[Dict[str, Any]]:
        """
        Get attendees for a specific event.
        
        Args:
            event_id: Google Calendar event ID
        
        Returns:
            List of attendee dictionaries
        """
        event = self.get_event_by_id(event_id)
        if event:
            return event.get('attendees', [])
        return []
    
    def search_events_by_keyword(
        self, 
        keyword: str, 
        max_results: int = 10,
        include_past: bool = True,
        include_future: bool = True,
        days_back: int = 30,
        days_forward: int = 30,
        past_only: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Search for calendar events containing a keyword in title or description.
        
        Args:
            keyword: Keyword to search for (e.g., client name)
            max_results: Maximum number of results to return
            include_past: Whether to search past events (default: True)
            include_future: Whether to search future events (default: True)
            days_back: Number of days to search back (default: 30)
            days_forward: Number of days to search forward (default: 30)
            past_only: If True, only return events that have already occurred (default: False)
        
        Returns:
            List of event dictionaries matching the keyword, sorted by start time (most recent first)
        """
        try:
            now = datetime.utcnow()
            matching_events = []
            
            # Search past events if requested
            if include_past:
                time_min = now - timedelta(days=days_back)
                time_max = now
                
                # Use pagination to get ALL events, not just first 50
                page_token = None
                all_past_events = []
                
                while True:
                    request_params = {
                        'calendarId': 'primary',
                        'timeMin': time_min.isoformat() + 'Z',
                        'timeMax': time_max.isoformat() + 'Z',
                        'maxResults': 2500,  # Maximum per page
                        'singleEvents': True,
                        'orderBy': 'startTime'
                    }
                    
                    if page_token:
                        request_params['pageToken'] = page_token
                    
                    events_result = self.service.events().list(**request_params).execute()
                    events = events_result.get('items', [])
                    all_past_events.extend(events)
                    
                    page_token = events_result.get('nextPageToken')
                    if not page_token:
                        break
                
                matching_events.extend(all_past_events)
            
            # Search future events if requested
            if include_future:
                time_min = now
                time_max = now + timedelta(days=days_forward)
                
                # Use pagination to get ALL events
                page_token = None
                all_future_events = []
                
                while True:
                    request_params = {
                        'calendarId': 'primary',
                        'timeMin': time_min.isoformat() + 'Z',
                        'timeMax': time_max.isoformat() + 'Z',
                        'maxResults': 2500,  # Maximum per page
                        'singleEvents': True,
                        'orderBy': 'startTime'
                    }
                    
                    if page_token:
                        request_params['pageToken'] = page_token
                    
                    events_result = self.service.events().list(**request_params).execute()
                    events = events_result.get('items', [])
                    all_future_events.extend(events)
                    
                    page_token = events_result.get('nextPageToken')
                    if not page_token:
                        break
                
                matching_events.extend(all_future_events)
            
            # Filter events that contain the keyword
            # Prioritize title matches over description/location matches
            keyword_lower = keyword.lower()
            title_matches = []
            other_matches = []
            
            for event in matching_events:
                title = event.get('summary', '').lower()
                description = event.get('description', '').lower()
                location = event.get('location', '').lower()
                
                # If past_only is True, check if event is in the past
                if past_only:
                    if not _is_event_in_past(event, now):
                        # Event is in the future, skip it
                        continue
                
                # Prioritize title matches
                if keyword_lower in title:
                    title_matches.append(event)
                elif (keyword_lower in description or keyword_lower in location):
                    other_matches.append(event)
                    # DON'T break early - collect ALL matching events first
                    # We'll sort them all and then return the most recent ones
            
            # Combine: title matches first, then others
            filtered_events = title_matches + other_matches
            
            # Sort by start time (most recent first)
            # Handle both dateTime (with time) and date (all-day) formats properly
            # IMPORTANT: Google API returns events in ascending order (oldest first),
            # so we need to reverse sort to get most recent first
            def get_sort_key(event):
                dt = extract_event_datetime(event)
                if not dt:
                    return datetime.min.replace(tzinfo=timezone.utc)  # Put events without dates at the end
                
                # Convert to naive UTC datetime for sorting (remove timezone)
                if dt.tzinfo:
                    return dt.astimezone(timezone.utc).replace(tzinfo=None)
                return dt
            
            # Sort by date (most recent first) - this ensures we get the latest meeting
            filtered_events.sort(key=get_sort_key, reverse=True)
            
            # Return only the requested number of results (most recent first)
            return filtered_events[:max_results]
        except Exception as e:
            raise Exception(f"Error searching calendar events: {str(e)}")
    
    def extract_zoom_meeting_id(self, event: Dict[str, Any]) -> Optional[str]:
        """
        Extract Zoom meeting ID from a calendar event.
        Checks description, location, and conferenceData.
        
        Args:
            event: Google Calendar event dictionary
        
        Returns:
            Zoom meeting ID (numeric string) or None if not found
        """
        import re
        
        # Check conferenceData first (most reliable)
        conference_data = event.get('conferenceData', {})
        entry_points = conference_data.get('entryPoints', [])
        for entry_point in entry_points:
            if entry_point.get('entryPointType') == 'video':
                uri = entry_point.get('uri', '')
                # Extract meeting ID from Zoom URI
                # Format: https://zoom.us/j/MEETING_ID or https://us02web.zoom.us/j/MEETING_ID
                match = re.search(r'zoom\.us/j/(\d+)', uri)
                if match:
                    return match.group(1)
        
        # Check description for Zoom links
        description = event.get('description', '')
        if description:
            # Look for zoom.us/j/MEETING_ID patterns
            matches = re.findall(r'zoom\.us/j/(\d+)', description, re.IGNORECASE)
            if matches:
                return matches[0]
            # Also check for zoom.us/join?pwd=...&confno=MEETING_ID
            match = re.search(r'zoom\.us/join.*[?&]confno=(\d+)', description, re.IGNORECASE)
            if match:
                return match.group(1)
        
        # Check location for Zoom links
        location = event.get('location', '')
        if location:
            matches = re.findall(r'zoom\.us/j/(\d+)', location, re.IGNORECASE)
            if matches:
                return matches[0]
        
        return None
    
    def extract_meeting_info(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract relevant meeting information from a calendar event.
        
        Args:
            event: Google Calendar event dictionary
        
        Returns:
            Structured meeting information
        """
        start = event.get('start', {})
        end = event.get('end', {})
        
        start_time = start.get('dateTime') or start.get('date')
        end_time = end.get('dateTime') or end.get('date')
        
        return {
            'id': event.get('id'),
            'title': event.get('summary', 'No Title'),
            'description': event.get('description', ''),
            'start_time': start_time,
            'end_time': end_time,
            'location': event.get('location', ''),
            'attendees': [
                {
                    'email': att.get('email'),
                    'name': att.get('displayName'),
                    'response_status': att.get('responseStatus')
                }
                for att in event.get('attendees', [])
            ],
            'organizer': {
                'email': event.get('organizer', {}).get('email'),
                'name': event.get('organizer', {}).get('displayName')
            },
            'hangout_link': event.get('hangoutLink'),
            'conference_data': event.get('conferenceData', {}),
            'zoom_meeting_id': self.extract_zoom_meeting_id(event)
        }
    
    def _parse_event_datetime(self, event: Dict[str, Any]) -> Optional[datetime]:
        """
        Parse the start datetime from a calendar event.
        Returns None if parsing fails.
        Returns naive UTC datetime (timezone removed) for database compatibility.
        """
        dt = extract_event_datetime(event)
        if not dt:
            return None
        
        # Normalize to UTC and return naive datetime for database storage
        if dt.tzinfo:
            dt = dt.astimezone(timezone.utc)
        return dt.replace(tzinfo=None)  # Return naive UTC datetime
    
    def get_most_recent_past_event(self, days_back: int = 180) -> Optional[Dict[str, Any]]:
        """
        Get the single most recent past event (closest to today but in the past).
        
        Args:
            days_back: How many days back to search (default: 180 days / 6 months)
        
        Returns:
            The most recent past event, or None if no events found
        """
        try:
            now = datetime.utcnow()
            time_min = now - timedelta(days=days_back)
            time_max = now
            
            # Get events from the past
            events_result = self.service.events().list(
                calendarId='primary',
                timeMin=time_min.isoformat() + 'Z',
                timeMax=time_max.isoformat() + 'Z',
                maxResults=100,  # Get enough to find the most recent
                singleEvents=True,
                orderBy='startTime'  # Google returns ascending, we'll reverse
            ).execute()
            
            events = events_result.get('items', [])
            if not events:
                return None
            
            # Parse and sort by datetime (most recent first)
            events_with_dt = []
            for event in events:
                dt = self._parse_event_datetime(event)
                if dt and dt < now.replace(tzinfo=None):
                    events_with_dt.append((dt, event))
            
            if not events_with_dt:
                return None
            
            # Sort by datetime descending (most recent first)
            events_with_dt.sort(key=lambda x: x[0], reverse=True)
            
            # Return the most recent past event
            return events_with_dt[0][1]
        except Exception as e:
            raise Exception(f"Error fetching most recent past event: {str(e)}")
    
    def get_recent_past_events(self, max_results: int = 3, days_back: int = 180) -> List[Dict[str, Any]]:
        """
        Get the N most recent past events (for user selection).
        
        Args:
            max_results: Number of events to return (default: 3)
            days_back: How many days back to search (default: 180 days / 6 months)
        
        Returns:
            List of the most recent past events, sorted by date (most recent first)
        """
        try:
            now = datetime.utcnow()
            time_min = now - timedelta(days=days_back)
            time_max = now
            
            # Get events from the past
            events_result = self.service.events().list(
                calendarId='primary',
                timeMin=time_min.isoformat() + 'Z',
                timeMax=time_max.isoformat() + 'Z',
                maxResults=100,  # Get enough to find the most recent
                singleEvents=True,
                orderBy='startTime'  # Google returns ascending, we'll reverse
            ).execute()
            
            events = events_result.get('items', [])
            if not events:
                return []
            
            # Parse and sort by datetime (most recent first)
            events_with_dt = []
            for event in events:
                dt = self._parse_event_datetime(event)
                if dt and dt < now.replace(tzinfo=None):
                    events_with_dt.append((dt, event))
            
            if not events_with_dt:
                return []
            
            # Sort by datetime descending (most recent first)
            events_with_dt.sort(key=lambda x: x[0], reverse=True)
            
            # Return top N most recent past events
            return [event for _, event in events_with_dt[:max_results]]
        except Exception as e:
            raise Exception(f"Error fetching recent past events: {str(e)}")
    
    def get_most_recent_past_event_by_keyword(
        self, 
        keyword: str, 
        days_back: int = 180
    ) -> Optional[Dict[str, Any]]:
        """
        Get the single most recent past event matching a keyword (e.g., client name).
        This is the event closest to today but in the past that matches the keyword.
        
        Args:
            keyword: Keyword to search for in title, description, or location
            days_back: How many days back to search (default: 180 days / 6 months)
        
        Returns:
            The most recent past event matching the keyword, or None if not found
        """
        try:
            now = datetime.utcnow()
            time_min = now - timedelta(days=days_back)
            time_max = now
            
            # Get events from the past
            events_result = self.service.events().list(
                calendarId='primary',
                timeMin=time_min.isoformat() + 'Z',
                timeMax=time_max.isoformat() + 'Z',
                maxResults=100,  # Get enough to find matches
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            
            events = events_result.get('items', [])
            if not events:
                return None
            
            keyword_lower = keyword.lower()
            matching_events = []
            
            # Filter events that contain the keyword
            for event in events:
                title = event.get('summary', '').lower()
                description = event.get('description', '').lower()
                location = event.get('location', '').lower()
                
                if (keyword_lower in title or 
                    keyword_lower in description or 
                    keyword_lower in location):
                    dt = self._parse_event_datetime(event)
                    if dt and dt < now.replace(tzinfo=None):
                        matching_events.append((dt, event))
            
            if not matching_events:
                return None
            
            # Sort by datetime descending (most recent first)
            matching_events.sort(key=lambda x: x[0], reverse=True)
            
            # Return the most recent past event matching the keyword
            return matching_events[0][1]
        except Exception as e:
            raise Exception(f"Error fetching most recent past event by keyword: {str(e)}")
    
    def get_next_upcoming_event(self, days_forward: int = 30) -> Optional[Dict[str, Any]]:
        """
        Get the single next upcoming event (closest to today but in the future).
        
        Args:
            days_forward: How many days forward to search (default: 30 days)
        
        Returns:
            The next upcoming event, or None if no events found
        """
        try:
            now = datetime.utcnow()
            time_min = now
            time_max = now + timedelta(days=days_forward)
            
            # Get upcoming events
            events_result = self.service.events().list(
                calendarId='primary',
                timeMin=time_min.isoformat() + 'Z',
                timeMax=time_max.isoformat() + 'Z',
                maxResults=10,  # We only need the first one
                singleEvents=True,
                orderBy='startTime'  # Google returns ascending (earliest first)
            ).execute()
            
            events = events_result.get('items', [])
            if not events:
                return None
            
            # Return the first event (earliest upcoming)
            return events[0]
        except Exception as e:
            raise Exception(f"Error fetching next upcoming event: {str(e)}")
    
    def get_next_upcoming_event_by_keyword(
        self, 
        keyword: str, 
        days_forward: int = 30
    ) -> Optional[Dict[str, Any]]:
        """
        Get the single next upcoming event matching a keyword (e.g., client name).
        
        Args:
            keyword: Keyword to search for in title, description, or location
            days_forward: How many days forward to search (default: 30 days)
        
        Returns:
            The next upcoming event matching the keyword, or None if not found
        """
        try:
            now = datetime.utcnow()
            time_min = now
            time_max = now + timedelta(days=days_forward)
            
            # Get upcoming events
            events_result = self.service.events().list(
                calendarId='primary',
                timeMin=time_min.isoformat() + 'Z',
                timeMax=time_max.isoformat() + 'Z',
                maxResults=50,  # Get enough to find matches
                singleEvents=True,
                orderBy='startTime'  # Google returns ascending (earliest first)
            ).execute()
            
            events = events_result.get('items', [])
            if not events:
                return None
            
            keyword_lower = keyword.lower()
            
            # Find the first (earliest) event matching the keyword
            for event in events:
                title = event.get('summary', '').lower()
                description = event.get('description', '').lower()
                location = event.get('location', '').lower()
                
                if (keyword_lower in title or 
                    keyword_lower in description or 
                    keyword_lower in location):
                    return event
            
            return None
        except Exception as e:
            raise Exception(f"Error fetching next upcoming event by keyword: {str(e)}")


# Simple function wrappers - no business logic, just API calls
def get_calendar_event_by_id(event_id: str) -> Optional[Dict[str, Any]]:
    """
    Get a calendar event by ID.
    
    Args:
        event_id: Google Calendar event ID
    
    Returns:
        Event dictionary or None
    """
    client = GoogleCalendarClient()
    return client.get_event_by_id(event_id)


def get_calendar_events_on_date(target_date: date) -> List[Dict[str, Any]]:
    """
    Get all calendar events on a specific date.
    
    Args:
        target_date: Date to get events for
    
    Returns:
        List of event dictionaries
    """
    client = GoogleCalendarClient()
    return client.get_events_on_date(target_date)


def get_calendar_events_by_time_range(start_time: datetime, end_time: datetime) -> List[Dict[str, Any]]:
    """
    Get calendar events within a time range.
    
    Args:
        start_time: Start of time range
        end_time: End of time range
    
    Returns:
        List of event dictionaries
    """
    client = GoogleCalendarClient()
    return client.get_events_by_time_range(start_time, end_time)


def extract_zoom_meeting_id_from_event(event: Dict[str, Any]) -> Optional[str]:
    """
    Extract Zoom meeting ID from a calendar event.
    
    Args:
        event: Calendar event dictionary
    
    Returns:
        Zoom meeting ID or None
    """
    client = GoogleCalendarClient()
    return client.extract_zoom_meeting_id(event)


def get_calendar_event_attendees(event_id: str) -> List[Dict[str, Any]]:
    """
    Get attendees for a calendar event.
    
    Args:
        event_id: Google Calendar event ID
    
    Returns:
        List of attendee dictionaries
    """
    client = GoogleCalendarClient()
    return client.get_event_attendees(event_id)


def search_calendar_events_by_keyword(
    keyword: str,
    max_results: int = 10,
    include_past: bool = True,
    include_future: bool = True,
    days_back: int = 30,
    days_forward: int = 30,
    past_only: bool = False
) -> List[Dict[str, Any]]:
    """
    Search for calendar events containing a keyword.
    
    Args:
        keyword: Keyword to search for
        max_results: Maximum number of results
        include_past: Whether to search past events
        include_future: Whether to search future events
        days_back: Number of days back to search
        days_forward: Number of days forward to search
        past_only: If True, only return past events
    
    Returns:
        List of event dictionaries
    """
    client = GoogleCalendarClient()
    return client.search_events_by_keyword(
        keyword, max_results, include_past, include_future,
        days_back, days_forward, past_only
    )

