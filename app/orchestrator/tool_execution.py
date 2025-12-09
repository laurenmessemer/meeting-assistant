"""Tool execution module - executes tools with structured data."""

from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from app.memory.repo import MemoryRepository
from app.tools.summarization import SummarizationTool
from app.tools.meeting_brief import MeetingBriefTool
from app.tools.followup import FollowUpTool
from app.orchestrator.integration_data_fetching import IntegrationDataFetcher
from app.orchestrator.meeting_finder import MeetingFinder
from app.memory.schemas import MeetingUpdate, DecisionCreate
from app.utils.date_utils import format_datetime_display


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
            integration_data = await self._prepare_summarization_data(
                prepared_data, user_id, client_id
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
        client_id: Optional[int]
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
        
        print(f"   EXTRACTED: meeting_id={meeting_id}, calendar_event_id={calendar_event_id}")
        print(f"   EXTRACTED: client_name='{client_name}', target_date={target_date}")
        print(f"   EXTRACTED: selected_meeting_number={selected_meeting_number}")
        
        # EARLY EXIT FIX: If the user selected a calendar event, use it directly.
        # This prevents database fallback from triggering when a calendar event is explicitly chosen.
        if calendar_event_id:
            print(f"   [EARLY EXIT] calendar_event_id provided ({calendar_event_id}), bypassing DB lookup and using calendar event directly")
            
            # Fetch the calendar event directly by ID
            from app.integrations.google_calendar_client import get_calendar_event_by_id
            try:
                calendar_event = get_calendar_event_by_id(calendar_event_id)
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
                print(f"   BRANCH: calendar_event found, processing...")
                event_data = await self.integration_data_fetcher.process_calendar_event_for_summarization(
                    calendar_event, user_id, client_id
                )
                if event_data.get("error"):
                    print(f"   ❌ ERROR processing calendar event: {event_data.get('error')}")
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
            print(f"[FOLLOWUP DEBUG] Step 1: Explicit meeting_id provided ({meeting_id}), fetching from database...")
            meeting = self.memory.get_meeting_by_id(meeting_id)
            if meeting:
                print(f"[FOLLOWUP DEBUG] Step 1: Meeting found in DB: {meeting.title} (client_id={meeting.client_id})")
                # Build structured_data from meeting
                result["structured_data"] = self._build_followup_structured_data(
                    meeting, client_id, user_id
                )
                result["meeting_id"] = meeting_id
                print(f"[FOLLOWUP DEBUG] Step 1: Returning result with meeting_id={meeting_id}")
                return result
            else:
                print(f"[FOLLOWUP DEBUG] Step 1: Meeting {meeting_id} NOT found in DB, continuing to fallback...")
        else:
            print(f"[FOLLOWUP DEBUG] Step 1: No explicit meeting_id provided — running meeting inference fallback")
        
        # Check persistent memory for last selected meeting before fallback logic
        if not meeting_id:
            persistent = context.get("persistent_memory", {}) if context else {}
            last_selected = persistent.get("last_selected_meeting")
            if last_selected and hasattr(last_selected, "value"):
                meeting_id = int(last_selected.value)
        
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
            meeting = self.memory.get_meeting_by_id(meeting_id)
            if meeting:
                result["structured_data"] = self._build_followup_structured_data(
                    meeting, client_id, user_id
                )
        
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
        integration_data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Execute the appropriate tool based on intent with prepared data."""
        # Extract memory from context (optional, safe if missing)
        # context may be None, user_memories may be empty
        user_memories = context.get("user_memories", []) if context else []
        past_context = user_memories[:5] if user_memories else None  # Max 5 items
        
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
        
        # Store decisions in memory if we have a meeting
        meeting_id = integration_data.get("meeting_id")
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
