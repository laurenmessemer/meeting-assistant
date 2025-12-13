"""Tool execution module - executes tools with structured data."""

import logging
from typing import Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session
from app.memory.repo import MemoryRepository
from app.tools.summarization import SummarizationTool
from app.tools.meeting_brief import MeetingBriefTool
from app.tools.followup import FollowUpTool
from app.orchestrator.integration_data_fetching import IntegrationDataFetcher
from app.orchestrator.meeting_finder import MeetingFinder
from app.memory.schemas import MeetingUpdate, DecisionCreate
from app.utils.date_utils import format_datetime_display
from app.utils.date_utils import extract_event_datetime
from datetime import datetime


logger = logging.getLogger(__name__)


class ToolExecutor:
    """Handles tool execution based on intent with structured data."""
    
    def __init__(
        self,
        db: Session,
        memory: MemoryRepository,
        summarization_tool: SummarizationTool,
        meeting_brief_tool: MeetingBriefTool,
        followup_tool: FollowUpTool,
        integration_data_fetcher: IntegrationDataFetcher
    ):
        self.db = db
        self.memory = memory
        self.summarization_tool = summarization_tool
        self.meeting_brief_tool = meeting_brief_tool
        self.followup_tool = followup_tool
        self.integration_data_fetcher = integration_data_fetcher
    
    async def prepare_integration_data(
        self,
        intent: str,
        prepared_data: Dict[str, Any],
        user_id: Optional[int],
        client_id: Optional[int],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Prepare integration data (find meetings, fetch transcripts, etc.).
        This is called before tool execution.
        """
        integration_data = {}
        
        if intent == "summarization":
            # Pass intent and message for last meeting auto-resolution
            # Try to get message from context or prepared_data
            message = None
            if context:
                message = context.get("message") or context.get("original_message")
            if not message:
                message = prepared_data.get("message")
            integration_data = await self._prepare_summarization_data(
                prepared_data, user_id, client_id, intent=intent, message=message
            )
        elif intent == "meeting_brief":
            integration_data = await self._prepare_meeting_brief_data(
                prepared_data, user_id, client_id
            )
        elif intent == "followup":
            integration_data = await self._prepare_followup_data(
                prepared_data, user_id, client_id, context
            )
        
        return integration_data
    
    async def _prepare_summarization_data(
        self,
        prepared_data: Dict[str, Any],
        user_id: Optional[int],
        client_id: Optional[int],
        intent: Optional[str] = None,
        message: Optional[str] = None
    ) -> Dict[str, Any]:
        """Prepare data for summarization tool."""
        print(f"\n[DEBUG TOOL] ToolExecutor._prepare_summarization_data() called")
        print(f"   INPUT: prepared_data={prepared_data}")
        print(f"   INPUT: user_id={user_id}, client_id={client_id}")
        
        meeting_id = prepared_data.get("meeting_id")
        calendar_event_id = prepared_data.get("calendar_event_id")
        client_name = prepared_data.get("client_name")
        target_date = prepared_data.get("target_date")
        selected_meeting_number = prepared_data.get("selected_meeting_number")
        
        # VALIDATION C3: Validate client_name exists in database
        if client_name is not None:
            # Validate client_name is a string
            if not isinstance(client_name, str):
                return {
                    "tool_name": "summarization",
                    "error": "Client name must be a string"
                }
            
            # Normalize: strip whitespace
            client_name = client_name.strip()
            
            # Validate client_name is not empty or whitespace-only
            if not client_name:
                return {
                    "tool_name": "summarization",
                    "error": f"Client '{client_name}' does not exist in database"
                }
            
            # Search for client by name (case-insensitive)
            matching_clients = self.memory.search_clients_by_name(client_name, user_id)
            
            # Check if any client name matches exactly (case-insensitive)
            found_client = None
            for client in matching_clients:
                if client.name.strip().lower() == client_name.lower():
                    found_client = client
                    break
            
            # If no exact match found, client does not exist
            if found_client is None:
                return {
                    "tool_name": "summarization",
                    "error": f"Client '{client_name}' does not exist in database"
                }
            
            # If both client_name and client_id are provided, validate consistency
            if client_id is not None:
                # Validate client_id is integer
                if not isinstance(client_id, int):
                    try:
                        client_id = int(client_id)
                    except (ValueError, TypeError):
                        return {
                            "tool_name": "summarization",
                            "error": "Invalid client_id format"
                        }
                
                # Check if client_name and client_id refer to the same client
                if found_client.id != client_id:
                    return {
                        "tool_name": "summarization",
                        "error": "Client name and client_id refer to different clients"
                    }
        
        print(f"   EXTRACTED: meeting_id={meeting_id}, calendar_event_id={calendar_event_id}")
        print(f"   EXTRACTED: client_name='{client_name}', target_date={target_date}")
        print(f"   EXTRACTED: selected_meeting_number={selected_meeting_number}")
        
        # EARLY EXIT FIX: If the user selected a calendar event, use it directly.
        # This prevents database fallback from triggering when a calendar event is explicitly chosen.
        if calendar_event_id:
            # VALIDATION A3.1: Validate calendar_event_id refers to exactly one event
            from app.integrations.google_calendar_client import get_calendar_event_by_id
            calendar_event = get_calendar_event_by_id(calendar_event_id)
            if calendar_event is None:
                return {
                    "tool_name": "summarization",
                    "error": f"Calendar event ID {calendar_event_id} does not exist in Google Calendar"
                }
            
            # VALIDATION A3.2: Validate calendar event date matches user's target_date
            # Date validated here for direct calendar_event_id path
            if target_date:
                event_dt = extract_event_datetime(calendar_event)
                if event_dt is None:
                    return {
                        "tool_name": "summarization",
                        "error": "Calendar event has invalid or missing date"
                    }
                
                # Compare dates (same day, ignoring time)
                if event_dt.date() != target_date.date():
                    return {
                        "tool_name": "summarization",
                        "error": f"Calendar event date ({event_dt.date()}) does not match requested date ({target_date.date()})"
                    }
            
            print(f"   [EARLY EXIT] calendar_event_id provided ({calendar_event_id}), bypassing DB lookup and using calendar event directly")
            
            # Fetch the calendar event directly by ID
            try:
                if calendar_event:
                    print(f"   ✅ Successfully fetched calendar event: {calendar_event.get('summary', 'Untitled')}")
                    
                    # Process the calendar event immediately (same as existing flow)
                    event_data = await self.integration_data_fetcher.process_calendar_event_for_summarization(
                        calendar_event, user_id, client_id
                    )
                    
                    if event_data.get("error"):
                        print(f"   ❌ ERROR processing calendar event: {event_data.get('error')}")
                        result = {
                            "meeting_id": None,
                            "calendar_event": None,
                            "meeting_options": None,
                            "structured_data": None,
                            "error": event_data["error"]
                        }
                        
                        # DIAGNOSTIC: Log error case
                        print(f"\n[DIAGNOSTIC SUMMARY] _prepare_summarization_data() - CALENDAR_EVENT_SELECTED_ERROR (EARLY EXIT)")
                        print(f"   message: '{prepared_data.get('message', 'N/A')}'")
                        print(f"   selected calendar_event_id: {calendar_event_id}")
                        print(f"   error: {event_data.get('error')}")
                        
                        return result
                    
                    # Successfully processed calendar event
                    result = {
                        "meeting_id": event_data.get("meeting_id"),
                        "calendar_event": calendar_event,
                        "meeting_options": None,
                        "structured_data": {
                            "transcript": event_data.get("transcript"),
                            "meeting_title": event_data.get("meeting_title"),
                            "meeting_date": event_data.get("meeting_date"),
                            "recording_date": event_data.get("recording_date"),
                            "attendees": event_data.get("attendees"),
                            "has_transcript": event_data.get("has_transcript", False)
                        }
                    }
                    
                    # DIAGNOSTIC: Log early exit success
                    print(f"\n[DIAGNOSTIC SUMMARY] _prepare_summarization_data() - CALENDAR_EVENT_SELECTED (EARLY EXIT)")
                    print(f"   message: '{prepared_data.get('message', 'N/A')}'")
                    print(f"   client_name: '{client_name}'")
                    print(f"   target_date: {target_date}")
                    print(f"   selected meeting_id: {meeting_id}")
                    print(f"   selected calendar_event_id: {calendar_event_id}")
                    print(f"   meeting source: CALENDAR_EVENT_SELECTED (bypassing all DB/fallback logic)")
                    print(f"   calendar_event metadata:")
                    print(f"      - summary: '{calendar_event.get('summary', 'N/A')}'")
                    print(f"      - id: '{calendar_event.get('id', 'N/A')}'")
                    print(f"      - start: {calendar_event.get('start', {}).get('dateTime', 'N/A')}")
                    print(f"   event_data metadata:")
                    print(f"      - meeting_id: {event_data.get('meeting_id')}")
                    print(f"      - meeting_title: '{event_data.get('meeting_title', 'N/A')}'")
                    print(f"      - meeting_date: '{event_data.get('meeting_date', 'N/A')}'")
                    print(f"      - has_transcript: {event_data.get('has_transcript', False)}")
                    print(f"      - transcript_length: {len(event_data.get('transcript', '')) if event_data.get('transcript') else 0}")
                    
                    return result
                else:
                    print(f"   ⚠️ Calendar event {calendar_event_id} not found, falling through to normal flow")
            except Exception as e:
                print(f"   ❌ Error fetching calendar event by ID: {e}, falling through to normal flow")
                # Fall through to normal flow if fetch fails
        
        result = {
            "meeting_id": None,
            "calendar_event": None,
            "meeting_options": None,
            "structured_data": None
        }
        
        # DIAGNOSTIC: Track original meeting_id to distinguish user selection from DB lookup
        original_meeting_id = meeting_id
        
        # Find meeting in database first
        if not meeting_id:
            print(f"   BRANCH: No meeting_id, searching database...")
            meeting_finder = MeetingFinder(self.db, self.memory)
            print(f"   CALLING: find_meeting_in_database(client_id={client_id}, user_id={user_id}, client_name='{client_name}', target_date={target_date})")
            db_meeting_id = meeting_finder.find_meeting_in_database(
                meeting_id=meeting_id,
                client_id=client_id,
                user_id=user_id,
                client_name=client_name,
                target_date=target_date
            )
            print(f"   RESULT: find_meeting_in_database returned meeting_id={db_meeting_id}")
            meeting_id = db_meeting_id
        
        # If we have a meeting_id, get data from database
        if meeting_id:
            print(f"   BRANCH: meeting_id found ({meeting_id}), fetching from database...")
            meeting = self.memory.get_meeting_by_id(meeting_id)
            if meeting:
                # VALIDATION A4.1: Validate database meeting date matches target_date
                if target_date and meeting.scheduled_time:
                    if meeting.scheduled_time.date() != target_date.date():
                        return {
                            "tool_name": "summarization",
                            "error": f"Meeting date ({meeting.scheduled_time.date()}) does not match requested date ({target_date.date()})"
                        }
                
                # VALIDATION A4.2: Validate year if user did NOT specify a year
                date_text = prepared_data.get("date_text")
                if date_text and meeting.scheduled_time:
                    # Check if date_text contains a year digit (4-digit year)
                    import re
                    has_year = bool(re.search(r'\d{4}', date_text))
                    if not has_year:
                        # User did not specify year, validate against current year
                        current_year = datetime.now().year
                        if meeting.scheduled_time.year != current_year:
                            return {
                                "tool_name": "summarization",
                                "error": f"Meeting year ({meeting.scheduled_time.year}) does not match current year ({current_year})"
                            }
                
                # VALIDATION A4.3: Validate calendar event date (if present) matches meeting date
                if calendar_event_id and meeting.scheduled_time:
                    from app.integrations.google_calendar_client import get_calendar_event_by_id
                    calendar_event = get_calendar_event_by_id(calendar_event_id)
                    if calendar_event:
                        event_dt = extract_event_datetime(calendar_event)
                        if event_dt and event_dt.date() != meeting.scheduled_time.date():
                            return {
                                "tool_name": "summarization",
                                "error": "Calendar event date does not match the database meeting date"
                            }
                
                print(f"   ✅ Meeting found in DB: {meeting.title} (scheduled_time={meeting.scheduled_time})")
                result["meeting_id"] = meeting_id
                result["structured_data"] = {
                    "transcript": meeting.transcript,
                    "meeting_title": meeting.title,
                    "meeting_date": format_datetime_display(meeting.scheduled_time),
                    "recording_date": format_datetime_display(meeting.scheduled_time),
                    "attendees": meeting.attendees,
                    "has_transcript": meeting.transcript is not None
                }
                print(f"   OUTPUT: Returning DB meeting data")
                
                # DIAGNOSTIC: Log meeting source and metadata
                meeting_source = "USER_SELECTED" if original_meeting_id else "DB_MATCH"
                print(f"\n[DIAGNOSTIC SUMMARY] _prepare_summarization_data() - {meeting_source}")
                print(f"   message: '{prepared_data.get('message', 'N/A')}'")
                print(f"   client_name: '{client_name}'")
                print(f"   target_date: {target_date}")
                print(f"   selected meeting_id: {meeting_id}")
                print(f"   selected calendar_event_id: {calendar_event_id}")
                print(f"   meeting source: {meeting_source}")
                print(f"   meeting metadata:")
                print(f"      - title: '{meeting.title}'")
                print(f"      - scheduled_time: {meeting.scheduled_time}")
                print(f"      - client_id: {meeting.client_id}")
                print(f"      - calendar_event_id: {meeting.calendar_event_id}")
                print(f"      - has_transcript: {meeting.transcript is not None}")
                print(f"      - transcript_length: {len(meeting.transcript) if meeting.transcript else 0}")
                
                return result
            else:
                print(f"   ❌ Meeting {meeting_id} not found in DB")
        
        # If no meeting in database, search calendar
        if not meeting_id:
            print(f"   BRANCH: No meeting_id, searching calendar...")
            print(f"   CALLING: find_meeting_in_calendar(client_name='{client_name}', target_date={target_date}, user_id={user_id})")
            meeting_finder = MeetingFinder(self.db, self.memory)
            calendar_event, meeting_options = meeting_finder.find_meeting_in_calendar(
                client_name=client_name,
                target_date=target_date,
                selected_meeting_number=selected_meeting_number,
                calendar_event_id=calendar_event_id,
                user_id=user_id
            )
            print(f"   RESULT: find_meeting_in_calendar returned calendar_event={calendar_event is not None}, meeting_options={meeting_options is not None}")
            
            # Auto-resolution: Attempt to auto-select "last meeting" when conditions are met
            if meeting_options and isinstance(meeting_options, list) and len(meeting_options) > 1:
                from app.orchestrator.last_meeting_resolver import resolve_last_meeting
                resolved_event = resolve_last_meeting(
                    message=message or "",
                    intent=intent or "",
                    target_date=target_date,
                    meeting_options=meeting_options
                )
                if resolved_event:
                    print(f"   [AUTO-RESOLUTION] Auto-selected most recent meeting from {len(meeting_options)} options")
                    calendar_event = resolved_event
                    meeting_options = None  # Clear options since we auto-selected
            
            # VALIDATION A3.3: Validate that multiple events don't match (ambiguous selection)
            if meeting_options and isinstance(meeting_options, list) and len(meeting_options) > 1:
                return {
                    "tool_name": "summarization",
                    "error": f"Multiple calendar events match the search criteria. Please select a specific meeting."
                }
            
            # If meeting options are returned, user needs to select
            if meeting_options:
                print(f"   BRANCH: meeting_options returned ({len(meeting_options)} options)")
                result["meeting_options"] = meeting_options
                print(f"   OUTPUT: Returning meeting options for user selection")
                
                # DIAGNOSTIC: Log meeting source and metadata
                print(f"\n[DIAGNOSTIC SUMMARY] _prepare_summarization_data() - USER_SELECTION_REQUIRED")
                print(f"   message: '{prepared_data.get('message', 'N/A')}'")
                print(f"   client_name: '{client_name}'")
                print(f"   target_date: {target_date}")
                print(f"   selected meeting_id: {meeting_id}")
                print(f"   selected calendar_event_id: {calendar_event_id}")
                print(f"   meeting source: USER_SELECTION_REQUIRED")
                print(f"   meeting_options count: {len(meeting_options)}")
                for i, opt in enumerate(meeting_options[:5], 1):  # Log first 5 options
                    opt_title = opt.get('title', getattr(opt, 'title', 'N/A')) if isinstance(opt, dict) else getattr(opt, 'title', 'N/A')
                    opt_date = opt.get('date', getattr(opt, 'date', 'N/A')) if isinstance(opt, dict) else getattr(opt, 'date', 'N/A')
                    print(f"      option {i}: '{opt_title}' on {opt_date}")
                
                return result
            
            # If we have a calendar event, process it
            if calendar_event:
                # VALIDATION A3.4: Validate calendar event date matches user's target_date
                # Only validate date here if this is the fallback search path (not direct calendar_event_id)
                if not calendar_event_id and target_date:
                    event_dt = extract_event_datetime(calendar_event)
                    if event_dt is None:
                        return {
                            "tool_name": "summarization",
                            "error": "Calendar event has invalid or missing date"
                        }
                    
                    # Compare dates (same day, ignoring time)
                    if event_dt.date() != target_date.date():
                        return {
                            "tool_name": "summarization",
                            "error": f"Calendar event date ({event_dt.date()}) does not match requested date ({target_date.date()})"
                        }
                
                print(f"   BRANCH: calendar_event found, processing...")
                print(f"   [DIAGNOSTIC] Calendar event details:")
                print(f"      calendar_event['id']: {calendar_event.get('id') if isinstance(calendar_event, dict) else 'N/A'}")
                print(f"      calendar_event['summary']: {calendar_event.get('summary') if isinstance(calendar_event, dict) else 'N/A'}")
                
                event_data = await self.integration_data_fetcher.process_calendar_event_for_summarization(
                    calendar_event, user_id, client_id
                )
                
                print(f"   [DIAGNOSTIC] process_calendar_event_for_summarization returned:")
                print(f"      meeting_id: {event_data.get('meeting_id')}")
                print(f"      has_transcript: {event_data.get('has_transcript', False)}")
                print(f"      error: {event_data.get('error', 'None')}")
                
                if event_data.get("error"):
                    print(f"   ❌ ERROR processing calendar event: {event_data.get('error')}")
                    print(f"   [DIAGNOSTIC] ❌ ERROR from process_calendar_event_for_summarization: {event_data.get('error')}")
                    result["error"] = event_data["error"]
                    
                    # DIAGNOSTIC: Log error case
                    print(f"\n[DIAGNOSTIC SUMMARY] _prepare_summarization_data() - ERROR")
                    print(f"   message: '{prepared_data.get('message', 'N/A')}'")
                    print(f"   client_name: '{client_name}'")
                    print(f"   target_date: {target_date}")
                    print(f"   selected meeting_id: {meeting_id}")
                    print(f"   selected calendar_event_id: {calendar_event_id}")
                    print(f"   meeting source: ERROR")
                    print(f"   error: {event_data.get('error')}")
                    
                    return result
                
                print(f"   ✅ Calendar event processed, meeting_id={event_data.get('meeting_id')}")
                print(f"   [DIAGNOSTIC] ✅ Successfully processed calendar event -> meeting_id={event_data.get('meeting_id')}")
                result["calendar_event"] = calendar_event
                result["meeting_id"] = event_data.get("meeting_id")
                result["structured_data"] = {
                    "transcript": event_data.get("transcript"),
                    "meeting_title": event_data.get("meeting_title"),
                    "meeting_date": event_data.get("meeting_date"),
                    "recording_date": event_data.get("recording_date"),
                    "attendees": event_data.get("attendees"),
                    "has_transcript": event_data.get("has_transcript", False)
                }
                
                # DIAGNOSTIC: Log meeting source and metadata
                print(f"\n[DIAGNOSTIC SUMMARY] _prepare_summarization_data() - CALENDAR_MATCH")
                print(f"   message: '{prepared_data.get('message', 'N/A')}'")
                print(f"   client_name: '{client_name}'")
                print(f"   target_date: {target_date}")
                print(f"   selected meeting_id: {meeting_id}")
                print(f"   selected calendar_event_id: {calendar_event_id}")
                print(f"   meeting source: CALENDAR_MATCH")
                print(f"   calendar_event metadata:")
                print(f"      - summary: '{calendar_event.get('summary', 'N/A')}'")
                print(f"      - id: '{calendar_event.get('id', 'N/A')}'")
                print(f"      - start: {calendar_event.get('start', {}).get('dateTime', 'N/A')}")
                print(f"   event_data metadata:")
                print(f"      - meeting_id: {event_data.get('meeting_id')}")
                print(f"      - meeting_title: '{event_data.get('meeting_title', 'N/A')}'")
                print(f"      - meeting_date: '{event_data.get('meeting_date', 'N/A')}'")
                print(f"      - has_transcript: {event_data.get('has_transcript', False)}")
                print(f"      - transcript_length: {len(event_data.get('transcript', '')) if event_data.get('transcript') else 0}")
            else:
                print(f"   ❌ No calendar_event found")
                
                # DIAGNOSTIC: Log no match case
                print(f"\n[DIAGNOSTIC SUMMARY] _prepare_summarization_data() - NO_MATCH")
                print(f"   message: '{prepared_data.get('message', 'N/A')}'")
                print(f"   client_name: '{client_name}'")
                print(f"   target_date: {target_date}")
                print(f"   selected meeting_id: {meeting_id}")
                print(f"   selected calendar_event_id: {calendar_event_id}")
                print(f"   meeting source: NO_MATCH")
        
        print(f"   OUTPUT: {result}")
        return result
    
    async def _prepare_meeting_brief_data(
        self,
        prepared_data: Dict[str, Any],
        user_id: Optional[int],
        client_id: Optional[int]
    ) -> Dict[str, Any]:
        """Prepare data for meeting brief tool."""
        calendar_event_id = prepared_data.get("calendar_event_id")
        client_name = prepared_data.get("client_name")
        
        result = {
            "structured_data": {}
        }
        
        # Get client context if client_id provided
        if client_id:
            client = self.memory.get_client_by_id(client_id)
            if client:
                client_name = client_name or client.name
        
        # Get previous meeting summary if client_name provided
        previous_meeting_summary = None
        if client_name and client_id:
            meetings = self.memory.get_meetings_by_client(client_id, limit=1)
            if meetings:
                previous_meeting = meetings[0]
                previous_meeting_summary = previous_meeting.summary
        
        # If calendar_event_id provided, get event details
        if calendar_event_id:
            event_details = self.integration_data_fetcher.get_calendar_event_details(calendar_event_id)
            if event_details:
                result["structured_data"] = {
                    "client_name": client_name,
                    "meeting_title": event_details.get("meeting_title"),
                    "meeting_date": event_details.get("meeting_date"),
                    "attendees": event_details.get("attendees"),
                    "previous_meeting_summary": previous_meeting_summary,
                    "client_context": None
                }
            else:
                result["structured_data"] = {
                    "client_name": client_name,
                    "meeting_title": None,
                    "meeting_date": None,
                    "attendees": None,
                    "previous_meeting_summary": previous_meeting_summary,
                    "client_context": None
                }
        else:
            result["structured_data"] = {
                "client_name": client_name,
                "meeting_title": None,
                "meeting_date": None,
                "attendees": None,
                "previous_meeting_summary": previous_meeting_summary,
                "client_context": None
            }
        
        return result
    
    async def _prepare_followup_data(
        self,
        prepared_data: Dict[str, Any],
        user_id: Optional[int],
        client_id: Optional[int],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Prepare data for followup tool using reusable pipeline pattern."""
        # DIAGNOSTIC: Log at the very TOP
        print(f"\n[FOLLOWUP DEBUG] _prepare_followup_data called")
        print(f"[FOLLOWUP DEBUG] selected_meeting_id: {prepared_data.get('meeting_id')}")
        print(f"[FOLLOWUP DEBUG] selected_calendar_event_id: {prepared_data.get('calendar_event_id')}")
        print(f"[FOLLOWUP DEBUG] user_id: {user_id}")
        print(f"[FOLLOWUP DEBUG] client_id: {client_id}")
        print(f"[FOLLOWUP DEBUG] prepared_data keys: {list(prepared_data.keys())}")
        print(f"[FOLLOWUP DEBUG] prepared_data full: {prepared_data}")
        if context:
            print(f"[FOLLOWUP DEBUG] context keys: {list(context.keys())}")
            print(f"[FOLLOWUP DEBUG] context.last_selected_meeting: {context.get('last_selected_meeting', 'NOT_FOUND')}")
            print(f"[FOLLOWUP DEBUG] context metadata: {context.get('metadata', {})}")
        else:
            print(f"[FOLLOWUP DEBUG] context: None (no context provided)")
        
        meeting_id = prepared_data.get("meeting_id")
        client_name = prepared_data.get("client_name")
        calendar_event_id = prepared_data.get("calendar_event_id")
        
        result = {
            "structured_data": {}
        }
        
        # Step 1: If meeting_id provided, fetch meeting from database
        if meeting_id:
            # Validate and cast meeting_id to integer
            if not isinstance(meeting_id, int):
                try:
                    meeting_id = int(meeting_id)
                except (ValueError, TypeError):
                    return {
                        "tool_name": "followup",
                        "error": "Invalid meeting_id format"
                    }
            
            # Validate meeting exists in database
            print(f"[FOLLOWUP DEBUG] Step 1: Explicit meeting_id provided ({meeting_id}), fetching from database...")
            meeting = self.memory.get_meeting_by_id(meeting_id)
            if meeting:
                # VALIDATION D2: Validate meeting.summary quality
                if meeting.summary is None:
                    return {
                        "tool_name": "followup",
                        "error": "No meeting summary available for follow-up."
                    }
                
                # 1: dict always indicates an error-like payload
                if isinstance(meeting.summary, dict):
                    return {
                        "tool_name": "followup",
                        "error": "Meeting summary is not valid text"
                    }
                
                # 2: non-string summaries (numbers, lists, booleans)
                if not isinstance(meeting.summary, str):
                    return {
                        "tool_name": "followup",
                        "error": "Meeting summary is not valid text"
                    }
                
                # 3: empty or whitespace-only strings
                if meeting.summary == "" or meeting.summary.strip() == "":
                    return {
                        "tool_name": "followup",
                        "error": "Meeting summary is empty"
                    }
                
                # 4: error-like string content
                summary_lower = meeting.summary.lower()
                if summary_lower.startswith("error"):
                    return {
                        "tool_name": "followup",
                        "error": "Meeting summary contains an error instead of valid text"
                    }
                
                # 5: partially generated or malformed summary indicators
                if summary_lower.startswith(("summary failed", "partial summary", "no summary")):
                    return {
                        "tool_name": "followup",
                        "error": "Meeting summary is incomplete or malformed"
                    }
                
                print(f"[FOLLOWUP DEBUG] Step 1: Meeting found in DB: {meeting.title} (client_id={meeting.client_id})")
                # Build structured_data from meeting
                result["structured_data"] = self._build_followup_structured_data(
                    meeting, client_id, user_id
                )
                result["meeting_id"] = meeting_id
                print(f"[FOLLOWUP DEBUG] Step 1: Returning result with meeting_id={meeting_id}")
                return result
            else:
                return {
                    "tool_name": "followup",
                    "error": f"Meeting ID {meeting_id} does not exist in database"
                }
        else:
            print(f"[FOLLOWUP DEBUG] Step 1: No explicit meeting_id provided — running meeting inference fallback")
        
        # Check persistent memory for last selected meeting before fallback logic
        if not meeting_id:
            persistent = context.get("persistent_memory", {}) if context else {}
            last_selected = persistent.get("last_selected_meeting")
            if last_selected and hasattr(last_selected, "value"):
                try:
                    meeting_id = int(last_selected.value)
                except (ValueError, TypeError):
                    return {
                        "tool_name": "followup",
                        "error": "Invalid meeting_id format"
                    }
                
                # Validate meeting from persistent memory still exists in database
                meeting = self.memory.get_meeting_by_id(meeting_id)
                if meeting is None:
                    return {
                        "tool_name": "followup",
                        "error": f"Meeting ID {meeting_id} does not exist in database"
                    }
        
        # Step 2: If NO meeting_id but client_id exists, use MeetingFinder
        if not meeting_id and client_id:
            print(f"[FOLLOWUP DEBUG] Step 2: No meeting_id but client_id exists ({client_id}), using MeetingFinder...")
            meeting_finder = MeetingFinder(self.db, self.memory)
            meeting_id = meeting_finder.find_meeting_in_database(
                meeting_id=None,
                client_id=client_id,
                user_id=user_id,
                client_name=client_name,
                for_followup=True
            )
            print(f"[FOLLOWUP DEBUG] Step 2: MeetingFinder returned meeting_id={meeting_id}")
        else:
            print(f"[FOLLOWUP DEBUG] Step 2: NOT triggered (meeting_id={meeting_id}, client_id={client_id})")
        
        # Step 2b: Fallback - If NO meeting_id and NO client_id, try finding by user_id
        if not meeting_id and client_id is None and user_id:
            print(f"[FOLLOWUP DEBUG] Step 2b: No meeting_id and NO client_id, searching by user_id fallback (user_id={user_id})...")
            meeting_finder = MeetingFinder(self.db, self.memory)
            meeting_id = meeting_finder.find_meeting_in_database(
                meeting_id=None,
                client_id=None,
                user_id=user_id,
                client_name=None,
                for_followup=True
            )
            print(f"[FOLLOWUP DEBUG] Step 2b: Result from user_id fallback: meeting_id = {meeting_id}")
        else:
            print(f"[FOLLOWUP DEBUG] Step 2b: NOT triggered (meeting_id={meeting_id}, client_id={client_id}, user_id={user_id})")
        
        # Step 3: If we now have a meeting_id, get data from database
        if meeting_id:
            # Validate and cast meeting_id to integer
            if not isinstance(meeting_id, int):
                try:
                    meeting_id = int(meeting_id)
                except (ValueError, TypeError):
                    return {
                        "tool_name": "followup",
                        "error": "Invalid meeting_id format"
                    }
            
            # Validate meeting from fallback search exists in database
            meeting = self.memory.get_meeting_by_id(meeting_id)
            if meeting:
                # VALIDATION D2: Validate meeting.summary quality
                if meeting.summary is None:
                    return {
                        "tool_name": "followup",
                        "error": "No meeting summary available for follow-up."
                    }
                
                # 1: dict always indicates an error-like payload
                if isinstance(meeting.summary, dict):
                    return {
                        "tool_name": "followup",
                        "error": "Meeting summary is not valid text"
                    }
                
                # 2: non-string summaries (numbers, lists, booleans)
                if not isinstance(meeting.summary, str):
                    return {
                        "tool_name": "followup",
                        "error": "Meeting summary is not valid text"
                    }
                
                # 3: empty or whitespace-only strings
                if meeting.summary == "" or meeting.summary.strip() == "":
                    return {
                        "tool_name": "followup",
                        "error": "Meeting summary is empty"
                    }
                
                # 4: error-like string content
                summary_lower = meeting.summary.lower()
                if summary_lower.startswith("error"):
                    return {
                        "tool_name": "followup",
                        "error": "Meeting summary contains an error instead of valid text"
                    }
                
                # 5: partially generated or malformed summary indicators
                if summary_lower.startswith(("summary failed", "partial summary", "no summary")):
                    return {
                        "tool_name": "followup",
                        "error": "Meeting summary is incomplete or malformed"
                    }
                
                result["structured_data"] = self._build_followup_structured_data(
                    meeting, client_id, user_id
                )
            else:
                return {
                    "tool_name": "followup",
                    "error": f"Meeting ID {meeting_id} does not exist in database"
                }
        
        # TEMPORARY DEBUG: Log final result
        print(f"[FOLLOWUP DEBUG] Final result: meeting_id in result = {result.get('meeting_id')}, has_structured_data = {bool(result.get('structured_data'))}")
        result["meeting_id"] = meeting_id  # TEMPORARY: Add meeting_id for debug visibility
        print(f"[FOLLOWUP DEBUG] After adding meeting_id: result.meeting_id = {result.get('meeting_id')}")
        
        return result
    
    def _build_followup_structured_data(
        self,
        meeting,
        client_id: Optional[int],
        user_id: Optional[int]
    ) -> Dict[str, Any]:
        """Build structured_data dict for followup tool from meeting object."""
        
        # VALIDATION C2: Validate client_id exists in database
        # Validate meeting.client_id if present
        if meeting.client_id is not None:
            # Validate and cast meeting.client_id to integer
            if not isinstance(meeting.client_id, int):
                try:
                    meeting.client_id = int(meeting.client_id)
                except (ValueError, TypeError):
                    return {
                        "tool_name": "followup",
                        "error": "Invalid client_id format in meeting record"
                    }
            
            # Validate client exists in database
            client = self.memory.get_client_by_id(meeting.client_id)
            if client is None:
                return {
                    "tool_name": "followup",
                    "error": f"Client ID {meeting.client_id} from meeting record does not exist in database"
                }
        
        # Validate client_id parameter if present
        if client_id is not None:
            # Validate and cast client_id to integer
            if not isinstance(client_id, int):
                try:
                    client_id = int(client_id)
                except (ValueError, TypeError):
                    return {
                        "tool_name": "followup",
                        "error": "Invalid client_id format"
                    }
            
            # Validate client exists in database
            client = self.memory.get_client_by_id(client_id)
            if client is None:
                return {
                    "tool_name": "followup",
                    "error": f"Client ID {client_id} does not exist in database"
                }
        
        # Get client information
        client_name = None
        client_email = None
        if meeting.client_id:
            client = self.memory.get_client_by_id(meeting.client_id)
            if client:
                client_name = client.name
                client_email = client.email
        elif client_id:
            # Fallback to provided client_id
            client = self.memory.get_client_by_id(client_id)
            if client:
                client_name = client.name
                client_email = client.email
        
        # Get decisions using memory repository
        db_decisions = self.memory.get_decisions_by_meeting_id(meeting.id)
        decisions = [
            {"description": d.description, "context": d.context}
            for d in db_decisions
        ]
        
        # Format meeting date using utility function
        meeting_date = format_datetime_display(meeting.scheduled_time)
        
        # Build structured_data using same pattern as summarization
        return {
            "meeting_summary": meeting.summary,
            "transcript": meeting.transcript,
            "meeting_title": meeting.title,
            "meeting_date": meeting_date,
            "client_name": client_name,
            "client_email": client_email,
            "attendees": meeting.attendees,
            "action_items": [],  # Can be populated from summary parsing if needed
            "decisions": decisions
        }
    
    async def execute(
        self,
        intent: str,
        message: str,
        context: Dict[str, Any],
        user_id: Optional[int],
        client_id: Optional[int],
        extracted_info: Dict[str, Any],
        prepared_data: Dict[str, Any],
        integration_data: Dict[str, Any],
        workflow: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """Execute the appropriate tool based on intent with prepared data."""
        # Extract memory from context (optional, safe if missing)
        # context may be None, user_memories may be empty
        user_memories = context.get("user_memories", []) if context else []
        past_context = user_memories[:5] if user_memories else None  # Max 5 items
        
        # Step 2: Workflow plumbing - backward compatibility guard
        # If no workflow or empty workflow, proceed with legacy routing logic unchanged.
        if not workflow or not workflow.get("steps"):
            pass  # Legacy mode, do nothing here yet
        
        # Step 3: Prerequisite checking
        if workflow and workflow.get("required_data"):
            prereq_error = self._check_prerequisites(
                workflow,
                context,
                prepared_data,
                integration_data,
                extracted_info,
                user_id,
                client_id
            )
            if prereq_error:
                return prereq_error
        
        # Step 4: Workflow execution coordinator
        if workflow and workflow.get("steps") and isinstance(workflow.get("steps"), list):
            return await self._execute_with_plan(
                workflow,
                context,
                prepared_data,
                integration_data,
                extracted_info,
                user_id,
                client_id,
                intent,
                message
            )
        
        try:
            if intent == "meeting_brief":
                return await self._execute_meeting_brief(integration_data, context)
            
            elif intent == "summarization":
                return await self._execute_summarization(
                    integration_data, user_id, client_id, context
                )
            
            elif intent == "followup":
                return await self._execute_followup(integration_data, context)
            
            else:
                return None
        
        except Exception as e:
            import traceback
            error_msg = f"An unexpected error occurred while executing {intent}: {str(e)}"
            print(f"❌ EXCEPTION in tool execution ({intent}): {str(e)}")
            print(f"📋 Traceback: {traceback.format_exc()}")
            return {
                "tool_name": intent,
                "error": error_msg
            }
    
    def _check_prerequisites(
        self,
        workflow: Dict[str, Any],
        context: Dict[str, Any],
        prepared_data: Dict[str, Any],
        integration_data: Dict[str, Any],
        extracted_info: Dict[str, Any],
        user_id: Optional[int],
        client_id: Optional[int]
    ) -> Optional[Dict[str, Any]]:
        """
        Check if all workflow prerequisites are satisfied.
        
        Args:
            workflow: Workflow plan with required_data
            context: Memory context
            prepared_data: Prepared data from data preparation
            integration_data: Integration data from preparation
            extracted_info: Extracted info from intent recognition
            user_id: User ID parameter
            client_id: Client ID parameter
        
        Returns:
            Error dict if prerequisites missing, None if all satisfied
        """
        # Extract required_data from workflow
        required_data = workflow.get("required_data", [])
        if not isinstance(required_data, list) or not required_data:
            return None  # No prerequisites declared, all satisfied
        
        # Prerequisites that must exist BEFORE workflow execution (input prerequisites)
        INPUT_PREREQUISITES = {
            "client_name",
            "meeting_date"  # Optional: accept if available, but don't block if missing
        }
        
        # Prerequisites that are PRODUCED BY workflow steps (output prerequisites)
        # These must NOT be validated before workflow execution
        OUTPUT_PREREQUISITES = {
            "meeting_id",  # Produced by find_meeting step
            "transcript"   # Produced by retrieve_transcript step
        }
        
        # Whitelist of allowed prerequisites
        ALLOWED_PREREQUISITES = {
            "meeting_id", "client_id", "user_id", "transcript",
            "meeting_title", "meeting_date", "calendar_event",
            "calendar_event_id", "meeting_summary", "structured_data",
            "client_context", "target_date", "client_name"
        }
        
        missing_prereqs = []
        
        for key in required_data:
            # Skip unknown prerequisites (LLM hallucination)
            if key not in ALLOWED_PREREQUISITES:
                # Silently skip unknown keys
                continue
            
            # Skip output prerequisites - these are produced by workflow steps
            # and should NOT block workflow execution
            if key in OUTPUT_PREREQUISITES:
                # Always pass for output prerequisites (workflow will produce them)
                continue
            
            # Only validate input prerequisites before workflow execution
            if key in INPUT_PREREQUISITES:
                # For meeting_date, it's optional - don't block if missing
                if key == "meeting_date":
                    # Check if available, but don't add to missing if not found
                    if not self._check_single_prerequisite(
                        key, context, prepared_data, integration_data,
                        extracted_info, user_id, client_id
                    ):
                        # meeting_date is optional, so don't add to missing_prereqs
                        pass
                else:
                    # For other input prerequisites (e.g., client_name), validate strictly
                    if not self._check_single_prerequisite(
                        key, context, prepared_data, integration_data,
                        extracted_info, user_id, client_id
                    ):
                        missing_prereqs.append(key)
            # For other prerequisites (not in INPUT_PREREQUISITES or OUTPUT_PREREQUISITES),
            # validate them as before (backward compatibility)
            elif key not in OUTPUT_PREREQUISITES:
                # Check prerequisite based on key
                if not self._check_single_prerequisite(
                    key, context, prepared_data, integration_data,
                    extracted_info, user_id, client_id
                ):
                    missing_prereqs.append(key)
        
        # Return error if any missing
        if missing_prereqs:
            return {
                "tool_name": "workflow",
                "error": f"Missing prerequisites: {', '.join(missing_prereqs)}"
            }
        
        return None  # All prerequisites satisfied
    
    def _check_single_prerequisite(
        self,
        key: str,
        context: Dict[str, Any],
        prepared_data: Dict[str, Any],
        integration_data: Dict[str, Any],
        extracted_info: Dict[str, Any],
        user_id: Optional[int],
        client_id: Optional[int]
    ) -> bool:
        """Check if a single prerequisite is satisfied."""
        
        if key == "meeting_id":
            value = integration_data.get("meeting_id") or prepared_data.get("meeting_id")
            return isinstance(value, int) and value > 0
        
        elif key == "client_id":
            value = client_id
            return isinstance(value, int) and value > 0
        
        elif key == "user_id":
            value = user_id
            return isinstance(value, int) and value > 0
        
        elif key == "transcript":
            value = integration_data.get("structured_data", {}).get("transcript")
            return isinstance(value, str) and value.strip() != ""
        
        elif key == "meeting_title":
            value = (
                integration_data.get("structured_data", {}).get("meeting_title") or
                extracted_info.get("meeting_title")
            )
            return isinstance(value, str) and value.strip() != ""
        
        elif key == "meeting_date":
            structured_date = integration_data.get("structured_data", {}).get("meeting_date")
            if structured_date and isinstance(structured_date, str) and structured_date.strip() != "":
                return True
            # Fallback: format target_date if available
            target_date = prepared_data.get("target_date")
            if target_date and isinstance(target_date, datetime):
                formatted = format_datetime_display(target_date)
                return isinstance(formatted, str) and formatted.strip() != ""
            return False
        
        elif key == "calendar_event":
            value = integration_data.get("calendar_event")
            return isinstance(value, dict) and len(value) > 0
        
        elif key == "calendar_event_id":
            value = (
                prepared_data.get("calendar_event_id") or
                integration_data.get("calendar_event", {}).get("id")
            )
            return isinstance(value, str) and value.strip() != ""
        
        elif key == "meeting_summary":
            value = integration_data.get("structured_data", {}).get("meeting_summary")
            return isinstance(value, str) and value.strip() != ""
        
        elif key == "client_name":
            value = (
                prepared_data.get("client_name") or
                extracted_info.get("client_name")
            )
            return isinstance(value, str) and value.strip() != ""
        
        elif key == "target_date":
            value = prepared_data.get("target_date")
            return isinstance(value, datetime)
        
        elif key == "structured_data":
            value = integration_data.get("structured_data")
            return isinstance(value, dict) and len(value) > 0
        
        elif key == "client_context":
            value = context.get("client_context")
            return isinstance(value, dict) and len(value) > 0
        
        return False  # Unknown key or not found
    
    async def _execute_with_plan(
        self,
        workflow: Dict[str, Any],
        context: Dict[str, Any],
        prepared_data: Dict[str, Any],
        integration_data: Dict[str, Any],
        extracted_info: Dict[str, Any],
        user_id: Optional[int],
        client_id: Optional[int],
        intent: str,
        message: str
    ) -> Optional[Dict[str, Any]]:
        """
        Execute workflow plan by coordinating multiple steps.
        
        Args:
            workflow: Workflow plan with steps array
            context: Memory context
            prepared_data: Prepared data from data preparation
            integration_data: Integration data from preparation (may be empty initially)
            extracted_info: Extracted info from intent recognition
            user_id: User ID parameter
            client_id: Client ID parameter
            intent: Original intent (for fallback)
            message: Original message (for fallback)
        
        Returns:
            Tool output dict if successful, error dict if failed, None if should fall back to legacy
        """
        # Safety guard: ensure integration_data is never None
        if integration_data is None:
            integration_data = {}
        
        # Initialize execution context
        execution_context = {
            "meeting_id": integration_data.get("meeting_id"),
            "calendar_event": integration_data.get("calendar_event"),
            "structured_data": integration_data.get("structured_data", {}),
            "step_results": []
        }
        executed_actions = {}
        
        # Step 5: Fallback tracking
        fallback_attempts: Dict[Tuple[int, str], int] = {}
        total_fallback_attempts_ref = {"count": 0}
        MAX_FALLBACKS_PER_STEP = 3
        MAX_TOTAL_FALLBACKS = 5
        
        # Extract and validate steps
        steps = workflow.get("steps", [])
        if not isinstance(steps, list) or not steps:
            return None  # Fall back to legacy routing
        
        # Filter out invalid steps
        valid_steps = []
        for i, step in enumerate(steps):
            if not isinstance(step, dict):
                continue  # Skip non-dict steps
            if not step.get("action") or not step.get("tool"):
                continue  # Skip steps missing required fields
            valid_steps.append((i, step))
        
        if not valid_steps:
            return None  # No valid steps, fall back to legacy
        
        # Loop through workflow steps
        for step_index, step in valid_steps:
            action = step.get("action")
            tool = step.get("tool")
            
            # Detect infinite loops
            action_count = executed_actions.get(action, 0)
            if action_count >= 3:
                return {
                    "tool_name": "workflow",
                    "error": f"Step '{action}' executed {action_count + 1} times, possible infinite loop",
                    "step": {"index": step_index, "action": action, "tool": tool}
                }
            executed_actions[action] = action_count + 1
            
            # Map step to action method
            try:
                step_result = await self._map_step_to_action(
                    step,
                    execution_context,
                    context,
                    prepared_data,
                    extracted_info,
                    user_id,
                    client_id
                )
            except Exception as e:
                return {
                    "tool_name": "workflow",
                    "error": f"Step '{action}' raised exception: {str(e)}",
                    "step": {"index": step_index, "action": action, "tool": tool},
                    "exception_type": type(e).__name__
                }
            
            # Handle skip_step callable
            if callable(step_result):
                step_result()
                logger.debug(f"Skipping step due to sanitized action: {step}")
                continue
            
            # Check for errors
            if step_result is None:
                # Step returned None (not found, etc.)
                # Step 5: Check for fallback before checking prerequisites
                if step.get("fallback"):
                    failure = {
                        "type": "not_found",
                        "step_result": None,
                        "step_action": action
                    }
                    fallback_result = await self._apply_fallback(
                        step,
                        failure,
                        execution_context,
                        context,
                        prepared_data,
                        extracted_info,
                        user_id,
                        client_id,
                        step_index=step_index,
                        fallback_attempts=fallback_attempts,
                        total_fallback_attempts_ref=total_fallback_attempts_ref,
                        MAX_FALLBACKS_PER_STEP=MAX_FALLBACKS_PER_STEP,
                        MAX_TOTAL_FALLBACKS=MAX_TOTAL_FALLBACKS
                    )
                    # Ref dict updated in-place by _apply_fallback()
                    
                    if fallback_result is not None and not fallback_result.get("error"):
                        # Fallback succeeded, update context and continue
                        execution_context = self._update_execution_context(
                            execution_context,
                            step,
                            fallback_result
                        )
                        execution_context["step_results"].append({
                            "index": step_index,
                            "action": action,
                            "tool": tool,
                            "result": fallback_result,
                            "fallback_used": True,
                            "fallback_action": fallback_result.get("fallback_action"),
                            "original_failure": failure
                        })
                        continue
                
                # No fallback or fallback failed, check if this is critical for next steps
                if step.get("prerequisites"):
                    # If step has prerequisites, it's likely critical
                    return {
                        "tool_name": "workflow",
                        "error": f"Step '{action}' did not produce required output",
                        "step": {"index": step_index, "action": action, "tool": tool}
                    }
                # Otherwise, continue (non-critical step)
                continue
            
            if isinstance(step_result, dict) and step_result.get("error"):
                # Step returned error
                # Step 5: Check for fallback before returning error
                if step.get("fallback"):
                    failure = {
                        "type": "error",
                        "step_result": step_result,
                        "step_action": action,
                        "error_message": step_result.get("error")
                    }
                    fallback_result = await self._apply_fallback(
                        step,
                        failure,
                        execution_context,
                        context,
                        prepared_data,
                        extracted_info,
                        user_id,
                        client_id,
                        step_index=step_index,
                        fallback_attempts=fallback_attempts,
                        total_fallback_attempts_ref=total_fallback_attempts_ref,
                        MAX_FALLBACKS_PER_STEP=MAX_FALLBACKS_PER_STEP,
                        MAX_TOTAL_FALLBACKS=MAX_TOTAL_FALLBACKS
                    )
                    # Ref dict updated in-place by _apply_fallback()
                    
                    if fallback_result is not None and not fallback_result.get("error"):
                        # Fallback succeeded, update context and continue
                        execution_context = self._update_execution_context(
                            execution_context,
                            step,
                            fallback_result
                        )
                        execution_context["step_results"].append({
                            "index": step_index,
                            "action": action,
                            "tool": tool,
                            "result": fallback_result,
                            "fallback_used": True,
                            "fallback_action": fallback_result.get("fallback_action"),
                            "original_failure": failure
                        })
                        continue
                
                # No fallback or fallback failed, return original error
                return {
                    "tool_name": step_result.get("tool_name", "workflow"),
                    "error": step_result.get("error"),
                    "step": {"index": step_index, "action": action, "tool": tool}
                }
            
            # Update execution context with step result
            execution_context = self._update_execution_context(
                execution_context,
                step,
                step_result
            )
            
            # Store step result for debugging
            execution_context["step_results"].append({
                "index": step_index,
                "action": action,
                "tool": tool,
                "result": step_result
            })
        
        # Determine final result based on last step
        if execution_context["step_results"]:
            last_result = execution_context["step_results"][-1]["result"]
            
            # If last step returned tool output, use it
            if isinstance(last_result, dict) and "tool_name" in last_result:
                return last_result
            
            # Otherwise, construct result from execution context
            return {
                "tool_name": "workflow",
                "result": execution_context.get("structured_data", {}),
                "execution_trace": execution_context["step_results"]
            }
        
        # No steps executed successfully
        return None  # Fall back to legacy routing
    
    async def _map_step_to_action(
        self,
        step: Dict[str, Any],
        execution_context: Dict[str, Any],
        context: Dict[str, Any],
        prepared_data: Dict[str, Any],
        extracted_info: Dict[str, Any],
        user_id: Optional[int],
        client_id: Optional[int]
    ) -> Optional[Dict[str, Any]]:
        """
        Map a workflow step to a concrete executor method.
        
        Args:
            step: Step dict with action, tool, prerequisites, fallback
            execution_context: Current execution context (updated by previous steps)
            context: Memory context
            prepared_data: Prepared data from data preparation
            extracted_info: Extracted info from intent recognition
            user_id: User ID parameter
            client_id: Client ID parameter
        
        Returns:
            Tool output dict if successful, error dict if failed, None if not found/not applicable
        """
        action = step.get("action")
        tool = step.get("tool")
        
        if not action or not tool:
            return None  # Invalid step, skip
        
        if action == "find_meeting":
            # Try database first
            meeting_finder = MeetingFinder(self.db, self.memory)
            meeting_id = meeting_finder.find_meeting_in_database(
                meeting_id=execution_context.get("meeting_id"),
                client_id=client_id,
                user_id=user_id,
                client_name=prepared_data.get("client_name") or extracted_info.get("client_name"),
                target_date=prepared_data.get("target_date")
            )
            
            if meeting_id:
                # Found in DB, get meeting object
                meeting = self.memory.get_meeting_by_id(meeting_id)
                if meeting:
                    execution_context["meeting_id"] = meeting_id
                    execution_context["structured_data"] = {
                        "meeting_title": meeting.title,
                        "meeting_date": format_datetime_display(meeting.scheduled_time),
                        "attendees": meeting.attendees,
                        "transcript": meeting.transcript,
                        "has_transcript": meeting.transcript is not None
                    }
                    return {"meeting_id": meeting_id, "source": "database"}
            
            # Try calendar search
            calendar_event, meeting_options = meeting_finder.find_meeting_in_calendar(
                client_name=prepared_data.get("client_name") or extracted_info.get("client_name"),
                target_date=prepared_data.get("target_date"),
                user_id=user_id,
                calendar_event_id=prepared_data.get("calendar_event_id")
            )
            
            if meeting_options:
                # Multiple matches, return options
                return {
                    "tool_name": "meeting_finder",
                    "meeting_options": meeting_options,
                    "requires_selection": True
                }
            
            if calendar_event:
                execution_context["calendar_event"] = calendar_event
                return {"calendar_event": calendar_event, "source": "calendar"}
            
            # Not found
            return None
        
        elif action == "skip_step":
            return lambda: None
        
        elif action == "retrieve_transcript":
            # Requires calendar_event or meeting_id
            calendar_event = execution_context.get("calendar_event")
            meeting_id = execution_context.get("meeting_id")
            
            # DIAGNOSTIC: Log the exact condition that triggers the error
            print(f"\n[DIAGNOSTIC] retrieve_transcript action check:")
            print(f"   calendar_event: {calendar_event is not None} ({'dict' if isinstance(calendar_event, dict) else type(calendar_event).__name__ if calendar_event else 'None'})")
            print(f"   meeting_id: {meeting_id}")
            print(f"   execution_context keys: {list(execution_context.keys())}")
            if calendar_event:
                print(f"   calendar_event keys: {list(calendar_event.keys()) if isinstance(calendar_event, dict) else 'N/A'}")
                print(f"   calendar_event['id']: {calendar_event.get('id') if isinstance(calendar_event, dict) else 'N/A'}")
            
            if not calendar_event and not meeting_id:
                print(f"   [DIAGNOSTIC] ❌ ERROR TRIGGERED: Both calendar_event and meeting_id are None/Missing")
                print(f"   [DIAGNOSTIC] This is the exact condition that causes: 'Cannot retrieve transcript: no calendar_event or meeting_id'")
                return {
                    "tool_name": "integration_fetcher",
                    "error": "Cannot retrieve transcript: no calendar_event or meeting_id"
                }
            else:
                print(f"   [DIAGNOSTIC] ✅ Condition passed: {'calendar_event' if calendar_event else ''}{' + ' if calendar_event and meeting_id else ''}{'meeting_id' if meeting_id else ''} is available")
            
            # Extract zoom_meeting_id from calendar_event
            if calendar_event:
                from app.integrations.google_calendar_client import extract_zoom_meeting_id_from_event
                zoom_meeting_id = extract_zoom_meeting_id_from_event(calendar_event)
                if zoom_meeting_id:
                    transcript = await self.integration_data_fetcher.fetch_zoom_transcript(
                        zoom_meeting_id,
                        extract_event_datetime(calendar_event)
                    )
                    if transcript:
                        execution_context["structured_data"]["transcript"] = transcript
                        execution_context["structured_data"]["has_transcript"] = True
                        return {"transcript": transcript}
            
            # Try getting transcript from meeting record
            if meeting_id:
                meeting = self.memory.get_meeting_by_id(meeting_id)
                if meeting and meeting.transcript:
                    execution_context["structured_data"]["transcript"] = meeting.transcript
                    execution_context["structured_data"]["has_transcript"] = True
                    return {"transcript": meeting.transcript}
            
            return None  # No transcript found
        
        elif action == "summarize":
            # Build integration_data from execution_context
            integration_data = {
                "meeting_id": execution_context.get("meeting_id"),
                "calendar_event": execution_context.get("calendar_event"),
                "structured_data": execution_context.get("structured_data", {})
            }
            
            # Call existing executor method
            return await self._execute_summarization(
                integration_data,
                user_id,
                client_id,
                context
            )
        
        elif action == "generate_followup":
            # Build integration_data from execution_context
            integration_data = {
                "meeting_id": execution_context.get("meeting_id"),
                "structured_data": execution_context.get("structured_data", {})
            }
            
            # Call existing executor method
            return await self._execute_followup(
                integration_data,
                context
            )
        
        elif action == "generate_brief":
            # Build integration_data from execution_context
            integration_data = {
                "structured_data": execution_context.get("structured_data", {})
            }
            
            # Call existing executor method
            return await self._execute_meeting_brief(
                integration_data,
                context
            )
        
        elif action == "retrieve_calendar_event":
            calendar_event_id = prepared_data.get("calendar_event_id")
            if not calendar_event_id:
                return {
                    "tool_name": "integration_fetcher",
                    "error": "Cannot retrieve calendar event: no calendar_event_id"
                }
            
            from app.integrations.google_calendar_client import get_calendar_event_by_id
            calendar_event = get_calendar_event_by_id(calendar_event_id)
            
            if calendar_event:
                execution_context["calendar_event"] = calendar_event
                return {"calendar_event": calendar_event}
            
            return None
        
        else:
            # Unknown action
            return {
                "tool_name": "workflow",
                "error": f"Unknown action '{action}'",
                "step": {"action": action, "tool": tool}
            }
    
    def _update_execution_context(
        self,
        execution_context: Dict[str, Any],
        step: Dict[str, Any],
        step_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Update execution context with step result.
        
        Normalizes different return formats into execution_context structure.
        """
        action = step.get("action")
        
        if action == "find_meeting":
            # step_result contains meeting_id or calendar_event
            if "meeting_id" in step_result:
                execution_context["meeting_id"] = step_result["meeting_id"]
            if "calendar_event" in step_result:
                execution_context["calendar_event"] = step_result["calendar_event"]
            if "structured_data" in step_result:
                execution_context["structured_data"].update(step_result["structured_data"])
        
        elif action == "retrieve_transcript":
            # step_result contains transcript
            if "transcript" in step_result:
                execution_context["structured_data"]["transcript"] = step_result["transcript"]
                execution_context["structured_data"]["has_transcript"] = True
        
        elif action == "summarize":
            # step_result is tool output: {"tool_name": "summarization", "result": {...}}
            if step_result.get("result"):
                summary = step_result["result"].get("summary")
                if summary:
                    execution_context["structured_data"]["meeting_summary"] = summary
        
        elif action == "generate_followup":
            # step_result is tool output: {"tool_name": "followup", "result": {...}}
            # Store result for final output
            execution_context["result"] = step_result.get("result")
        
        elif action == "retrieve_calendar_event":
            # step_result contains calendar_event
            if "calendar_event" in step_result:
                execution_context["calendar_event"] = step_result["calendar_event"]
        
        return execution_context
    
    async def _apply_fallback(
        self,
        step: Dict[str, Any],
        failure: Dict[str, Any],
        execution_context: Dict[str, Any],
        context: Dict[str, Any],
        prepared_data: Dict[str, Any],
        extracted_info: Dict[str, Any],
        user_id: Optional[int],
        client_id: Optional[int],
        step_index: int,
        fallback_attempts: Dict[Tuple[int, str], int],
        total_fallback_attempts_ref: Dict[str, int],
        MAX_FALLBACKS_PER_STEP: int,
        MAX_TOTAL_FALLBACKS: int
    ) -> Optional[Dict[str, Any]]:
        """
        Apply fallback action when primary step fails.
        
        Args:
            step: Original step dict with fallback definition
            failure: Failure information (None return or error dict)
            execution_context: Current execution context
            context: Memory context
            prepared_data: Prepared data from data preparation
            extracted_info: Extracted info from intent recognition
            user_id: User ID parameter
            client_id: Client ID parameter
            step_index: Index of the step in workflow
            fallback_attempts: Dict tracking attempts per (step_index, fallback_action)
            total_fallback_attempts_ref: Mutable dict with "count" key for total attempts
            MAX_FALLBACKS_PER_STEP: Maximum fallback attempts per step
            MAX_TOTAL_FALLBACKS: Maximum total fallback attempts
        
        Returns:
            Fallback result dict if successful, error dict if failed, None if not applicable
        """
        # Normalize fallback definition
        fallback_def = step.get("fallback")
        if fallback_def is None:
            return None
        
        # Normalize to list
        if isinstance(fallback_def, dict):
            fallback_chain = [fallback_def]
        elif isinstance(fallback_def, list):
            fallback_chain = fallback_def
        else:
            return {
                "tool_name": "workflow",
                "error": "Invalid fallback format: must be dict or list",
                "step": {"index": step_index, "action": step.get("action")}
            }
        
        # Validate each fallback object
        for fallback in fallback_chain:
            if not isinstance(fallback, dict):
                return {
                    "tool_name": "workflow",
                    "error": "Invalid fallback format: fallback must be dict",
                    "step": {"index": step_index, "action": step.get("action")}
                }
            if not fallback.get("action") or not isinstance(fallback.get("action"), str):
                return {
                    "tool_name": "workflow",
                    "error": "Invalid fallback format: fallback must have 'action' string",
                    "step": {"index": step_index, "action": step.get("action")}
                }
        
        # Determine failure condition
        failure_type = failure.get("type")
        step_action = failure.get("step_action", "")
        error_message = failure.get("error_message", "")
        
        failure_condition = None
        if failure_type == "not_found":
            # Map based on step action
            if step_action == "find_meeting":
                failure_condition = "no_db_match"
            elif step_action == "retrieve_calendar_event":
                failure_condition = "no_calendar_match"
            else:
                failure_condition = "no_db_match"  # Default
        elif failure_type == "error":
            # Map based on error message content
            error_lower = error_message.lower() if error_message else ""
            if "transcript" in error_lower and ("not found" in error_lower or "no transcript" in error_lower or "missing" in error_lower):
                failure_condition = "no_transcript"
            elif "unknown action" in error_lower or "unknown" in error_lower:
                failure_condition = "unknown_action"
            else:
                failure_condition = "tool_failure"
        elif failure_type == "exception":
            failure_condition = "tool_failure"
        else:
            failure_condition = "tool_failure"  # Default
        
        # Iterate through fallback chain
        for fallback in fallback_chain:
            fallback_action = fallback.get("action")
            fallback_conditions = fallback.get("conditions", [])
            
            # Check if conditions match
            if failure_condition not in fallback_conditions:
                continue  # Skip this fallback
            
            # Check per-step limits
            fallback_key = (step_index, fallback_action)
            attempt_count = fallback_attempts.get(fallback_key, 0)
            max_attempts = fallback.get("max_attempts", 1)
            
            if attempt_count >= max_attempts:
                continue  # Skip this fallback (limit exceeded)
            
            # Check global limits
            if total_fallback_attempts_ref["count"] >= MAX_TOTAL_FALLBACKS:
                return {
                    "tool_name": "workflow",
                    "error": f"Maximum total fallback attempts ({MAX_TOTAL_FALLBACKS}) exceeded",
                    "step": {"index": step_index, "action": step.get("action")},
                    "original_failure": failure
                }
            
            # Increment counters
            fallback_attempts[fallback_key] = attempt_count + 1
            total_fallback_attempts_ref["count"] += 1
            
            # Execute fallback action
            try:
                fallback_result = None
                
                if fallback_action == "resolve_meeting_from_calendar":
                    # Use existing calendar search logic
                    meeting_finder = MeetingFinder(self.db, self.memory)
                    calendar_event, meeting_options = meeting_finder.find_meeting_in_calendar(
                        client_name=prepared_data.get("client_name") or extracted_info.get("client_name"),
                        target_date=prepared_data.get("target_date"),
                        user_id=user_id,
                        calendar_event_id=prepared_data.get("calendar_event_id")
                    )
                    
                    if meeting_options:
                        # Multiple matches
                        fallback_result = {
                            "tool_name": "meeting_finder",
                            "meeting_options": meeting_options,
                            "requires_selection": True,
                            "fallback_action": fallback_action
                        }
                    elif calendar_event:
                        execution_context["calendar_event"] = calendar_event
                        fallback_result = {
                            "calendar_event": calendar_event,
                            "source": "fallback_calendar",
                            "fallback_action": fallback_action
                        }
                    else:
                        # Not found
                        fallback_result = None
                
                elif fallback_action == "use_last_selected_meeting":
                    # Read from persistent memory
                    persistent = context.get("persistent_memory", {})
                    last_selected = persistent.get("last_selected_meeting")
                    
                    if last_selected and hasattr(last_selected, 'value') and last_selected.value:
                        try:
                            meeting_id = int(last_selected.value)
                            meeting = self.memory.get_meeting_by_id(meeting_id)
                            if meeting:
                                execution_context["meeting_id"] = meeting_id
                                execution_context["structured_data"] = {
                                    "meeting_title": meeting.title,
                                    "meeting_date": format_datetime_display(meeting.scheduled_time),
                                    "attendees": meeting.attendees,
                                    "transcript": meeting.transcript,
                                    "has_transcript": meeting.transcript is not None
                                }
                                fallback_result = {
                                    "meeting_id": meeting_id,
                                    "source": "fallback_last_selected",
                                    "fallback_action": fallback_action
                                }
                            else:
                                fallback_result = None
                        except (ValueError, TypeError):
                            fallback_result = None  # Invalid meeting_id, continue to next fallback
                    else:
                        # Not found
                        fallback_result = None
                
                elif fallback_action == "force_summarization":
                    # Reuse existing summarization path
                    # Build integration_data from execution_context
                    integration_data = {
                        "meeting_id": execution_context.get("meeting_id"),
                        "calendar_event": execution_context.get("calendar_event"),
                        "structured_data": execution_context.get("structured_data", {})
                    }
                    
                    # Check if we have transcript and meeting_id
                    if integration_data.get("structured_data", {}).get("transcript") and integration_data.get("meeting_id"):
                        # Call existing executor method
                        result = await self._execute_summarization(
                            integration_data,
                            user_id,
                            client_id,
                            context
                        )
                        
                        if result and not result.get("error"):
                            # Extract summary from result
                            if result.get("result", {}).get("summary"):
                                execution_context["structured_data"]["meeting_summary"] = result["result"]["summary"]
                                fallback_result = {
                                    "tool_name": "summarization",
                                    "result": result.get("result"),
                                    "fallback_action": fallback_action
                                }
                            else:
                                fallback_result = None
                        else:
                            fallback_result = None
                    else:
                        # Cannot force summarization (missing transcript or meeting_id)
                        fallback_result = None
                
                elif fallback_action == "skip_step":
                    # Return dict to indicate step skipped (non-critical)
                    fallback_result = {
                        "skipped": True,
                        "fallback_action": fallback_action
                    }
                
                elif fallback_action == "ask_user_for_meeting":
                    # Return structured dict for user selection
                    message = fallback.get("message_to_user") or "Which meeting did you mean?"
                    options = execution_context.get("meeting_options") or []
                    
                    fallback_result = {
                        "tool_name": "workflow",
                        "requires_user_selection": True,
                        "message": message,
                        "options": options,
                        "fallback_action": fallback_action
                    }
                
                else:
                    # Unknown fallback action
                    return {
                        "tool_name": "workflow",
                        "error": f"Unknown fallback action '{fallback_action}'",
                        "step": {"index": step_index, "action": step.get("action")},
                        "fallback_action": fallback_action,
                        "original_failure": failure
                    }
                
                # Check if fallback succeeded
                if fallback_result is not None:
                    # Check if it's an error dict
                    if isinstance(fallback_result, dict) and fallback_result.get("error"):
                        # Fallback returned error, try next in chain
                        continue
                    # Fallback succeeded, return result
                    return fallback_result
                
                # Fallback failed (returned None), try next in chain
                continue
                    
            except Exception as e:
                # Exception during fallback execution
                return {
                    "tool_name": "workflow",
                    "error": f"Fallback '{fallback_action}' raised exception: {str(e)}",
                    "step": {"index": step_index, "action": step.get("action")},
                    "exception_type": type(e).__name__,
                    "fallback_action": fallback_action,
                    "original_failure": failure
                }
        
        # All fallbacks in chain failed
        return {
            "tool_name": "workflow",
            "error": f"All fallbacks failed for step '{step.get('action')}'",
            "step": {"index": step_index, "action": step.get("action")},
            "fallback_action": fallback_chain[-1].get("action") if fallback_chain else None,
            "original_failure": failure
        }
    
    async def _execute_meeting_brief(
        self,
        integration_data: Dict[str, Any],
        context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Execute meeting brief tool."""
        # Extract memory from context (optional, safe if missing)
        user_memories = context.get("user_memories", []) if context else []
        past_context = user_memories[:5] if user_memories else None  # Max 5 items
        
        structured_data = integration_data.get("structured_data", {})
        
        # Check if we have enough context
        if not structured_data.get("client_name"):
            return None
        
        # Call tool with structured input
        result = await self.meeting_brief_tool.generate_brief(
            **structured_data,
            past_context=past_context
        )
        
        return {
            "tool_name": "meeting_brief",
            "result": result
        }
    
    async def _execute_summarization(
        self,
        integration_data: Dict[str, Any],
        user_id: Optional[int],
        client_id: Optional[int],
        context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Execute summarization tool."""
        # Safety guard: ensure integration_data is never None
        if integration_data is None:
            integration_data = {}
        
        # Extract memory from context (optional, safe if missing)
        user_memories = context.get("user_memories", []) if context else []
        past_context = user_memories[:5] if user_memories else None  # Max 5 items
        
        # Check if we need user selection
        if integration_data.get("meeting_options"):
            return {
                "tool_name": "summarization",
                "result": None,
                "meeting_options": integration_data["meeting_options"],
                "requires_selection": True
            }
        
        # Check for errors
        if integration_data.get("error"):
            return {
                "tool_name": "summarization",
                "error": integration_data["error"]
            }
        
        structured_data = integration_data.get("structured_data")
        if not structured_data:
            return {
                "tool_name": "summarization",
                "error": "No meeting found to summarize."
            }
        
        # Validate we have transcript if has_transcript is True
        if structured_data.get("has_transcript") and not structured_data.get("transcript"):
            title = structured_data.get("meeting_title", "this meeting")
            return {
                "tool_name": "summarization",
                "error": (
                    f"No transcript available for {title}. "
                    "To summarize a meeting, you need a Zoom recording with transcript that matches the calendar event."
                )
            }
        
        # VALIDATION B1: Additional transcript validation
        transcript = structured_data.get("transcript")
        if transcript is not None:
            # 1: dict always indicates an error-like payload
            if isinstance(transcript, dict):
                return {
                    "tool_name": "summarization",
                    "error": "Transcript contains an error instead of valid text"
                }
            
            # 2: non-string transcripts (numbers, lists, booleans)
            if not isinstance(transcript, str):
                return {
                    "tool_name": "summarization",
                    "error": "Transcript is not valid text"
                }
            
            # 3: empty or whitespace-only strings
            if transcript == "" or transcript.strip() == "":
                return {
                    "tool_name": "summarization",
                    "error": "Transcript is empty"
                }
            
            # 4: error-like string content
            if transcript.lower().startswith("error"):
                return {
                    "tool_name": "summarization",
                    "error": "Transcript contains an error instead of valid text"
                }
        
        # Call tool with structured input
        # DIAGNOSTIC: Extract meeting_id and calendar_event_id for logging
        diagnostic_meeting_id = integration_data.get("meeting_id")
        diagnostic_calendar_event_id = integration_data.get("calendar_event", {}).get("id") if integration_data.get("calendar_event") else None
        
        result = await self.summarization_tool.summarize_meeting(
            **structured_data,
            past_context=past_context,
            meeting_id=diagnostic_meeting_id,
            calendar_event_id=diagnostic_calendar_event_id,
            user_id=user_id
        )
        
        # Check if result has error
        if result.get("error"):
            return {
                "tool_name": "summarization",
                "error": result["error"]
            }
        
        # Validate meeting_id exists in database before using it
        meeting_id = integration_data.get("meeting_id")
        if meeting_id:
            # Validate and cast meeting_id to integer
            if not isinstance(meeting_id, int):
                try:
                    meeting_id = int(meeting_id)
                except (ValueError, TypeError):
                    return {
                        "tool_name": "summarization",
                        "error": "Invalid meeting_id format"
                    }
            
            # Now meeting_id is guaranteed to be an integer, validate it exists in database
            meeting = self.memory.get_meeting_by_id(meeting_id)
            if meeting is None:
                return {
                    "tool_name": "summarization",
                    "error": f"Meeting ID {meeting_id} does not exist in database"
                }
        
        # Store decisions in memory if we have a meeting
        if meeting_id and result.get("decisions") and client_id:
            decisions_to_save = []
            for decision_data in result.get("decisions", []):
                if isinstance(decision_data, dict):
                    decisions_to_save.append(
                        DecisionCreate(
                            meeting_id=meeting_id,
                            client_id=client_id,
                            description=decision_data.get("description", ""),
                            context=decision_data.get("context"),
                        )
                    )
            if decisions_to_save:
                self.memory.save_decisions(decisions_to_save)
        
        # Update meeting with summary if we have a meeting_id
        if meeting_id and result.get("summary"):
            self.memory.update_meeting(
                meeting_id,
                MeetingUpdate(summary=result.get("summary"))
            )
            
            # Save last selected meeting to persistent memory
            if user_id:
                # Only attempt to pull a calendar event ID if integration_data exists
                calendar_event_id = None
                if integration_data and isinstance(integration_data, dict):
                    calendar_event_id = (
                        integration_data.get("calendar_event", {}) or {}
                    ).get("id")
                
                self.memory.save_memory_by_key(
                    user_id=user_id,
                    client_id=client_id,
                    key="last_selected_meeting",
                    value=str(meeting_id),
                    extra_data={"calendar_event_id": calendar_event_id}
                )
        
        return {
            "tool_name": "summarization",
            "result": result
        }
    
    async def _execute_followup(
        self,
        integration_data: Dict[str, Any],
        context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Execute follow-up tool."""
        # Extract memory from context (optional, safe if missing)
        user_memories = context.get("user_memories", []) if context else []
        past_context = user_memories[:5] if user_memories else None  # Max 5 items
        
        structured_data = integration_data.get("structured_data", {})
        
        if not structured_data.get("meeting_summary"):
            return {
                "tool_name": "followup",
                "error": "No meeting summary available for follow-up."
            }
        
        # VALIDATION D1: Validate meeting_summary quality
        meeting_summary = structured_data.get("meeting_summary")
        if meeting_summary is not None:
            # 1: dict always indicates an error-like payload
            if isinstance(meeting_summary, dict):
                return {
                    "tool_name": "followup",
                    "error": "Meeting summary is not valid text"
                }
            
            # 2: non-string summaries (numbers, lists, booleans)
            if not isinstance(meeting_summary, str):
                return {
                    "tool_name": "followup",
                    "error": "Meeting summary is not valid text"
                }
            
            # 3: empty or whitespace-only strings
            if meeting_summary == "" or meeting_summary.strip() == "":
                return {
                    "tool_name": "followup",
                    "error": "Meeting summary is empty"
                }
            
            # 4: error-like string content
            summary_lower = meeting_summary.lower()
            if summary_lower.startswith("error"):
                return {
                    "tool_name": "followup",
                    "error": "Meeting summary contains an error instead of valid text"
                }
            
            # 5: partially generated or malformed summary indicators
            if summary_lower.startswith(("summary failed", "partial summary", "no summary")):
                return {
                    "tool_name": "followup",
                    "error": "Meeting summary is incomplete or malformed"
                }
        
        # DIAGNOSTIC: Extract meeting identifiers for logging
        diagnostic_meeting_id = integration_data.get("meeting_id")
        diagnostic_calendar_event_id = integration_data.get("calendar_event", {}).get("id") if integration_data.get("calendar_event") else None
        diagnostic_meeting_source = integration_data.get("meeting_source", "unknown")
        
        # Call tool with structured input
        result = await self.followup_tool.generate_followup(
            **structured_data,
            past_context=past_context,
            meeting_id=diagnostic_meeting_id,
            calendar_event_id=diagnostic_calendar_event_id,
            meeting_source=diagnostic_meeting_source
        )
        
        return {
            "tool_name": "followup",
            "result": result
        }
