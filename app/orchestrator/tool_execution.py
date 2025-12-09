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
                prepared_data, user_id, client_id
            )
        
        return integration_data
    
    async def _prepare_summarization_data(
        self,
        prepared_data: Dict[str, Any],
        user_id: Optional[int],
        client_id: Optional[int]
    ) -> Dict[str, Any]:
        """Prepare data for summarization tool."""
        meeting_id = prepared_data.get("meeting_id")
        calendar_event_id = prepared_data.get("calendar_event_id")
        client_name = prepared_data.get("client_name")
        target_date = prepared_data.get("target_date")
        selected_meeting_number = prepared_data.get("selected_meeting_number")
        
        result = {
            "meeting_id": None,
            "calendar_event": None,
            "meeting_options": None,
            "structured_data": None
        }
        
        # Find meeting in database first
        if not meeting_id:
            meeting_finder = MeetingFinder(self.db, self.memory)
            meeting_id = meeting_finder.find_meeting_in_database(
                meeting_id=meeting_id,
                client_id=client_id,
                user_id=user_id,
                client_name=client_name
            )
        
        # If we have a meeting_id, get data from database
        if meeting_id:
            meeting = self.memory.get_meeting_by_id(meeting_id)
            if meeting:
                result["meeting_id"] = meeting_id
                result["structured_data"] = {
                    "transcript": meeting.transcript,
                    "meeting_title": meeting.title,
                    "meeting_date": format_datetime_display(meeting.scheduled_time),
                    "recording_date": format_datetime_display(meeting.scheduled_time),
                    "attendees": meeting.attendees,
                    "has_transcript": meeting.transcript is not None
                }
                return result
        
        # If no meeting in database, search calendar
        if not meeting_id:
            meeting_finder = MeetingFinder(self.db, self.memory)
            calendar_event, meeting_options = meeting_finder.find_meeting_in_calendar(
                client_name=client_name,
                target_date=target_date,
                selected_meeting_number=selected_meeting_number,
                calendar_event_id=calendar_event_id,
                user_id=user_id
            )
            
            # If meeting options are returned, user needs to select
            if meeting_options:
                result["meeting_options"] = meeting_options
                return result
            
            # If we have a calendar event, process it
            if calendar_event:
                event_data = await self.integration_data_fetcher.process_calendar_event_for_summarization(
                    calendar_event, user_id, client_id
                )
                if event_data.get("error"):
                    result["error"] = event_data["error"]
                    return result
                
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
        client_id: Optional[int]
    ) -> Dict[str, Any]:
        """Prepare data for followup tool."""
        meeting_id = prepared_data.get("meeting_id")
        
        result = {
            "structured_data": {}
        }
        
        # If no meeting_id and we have client_id, get most recent meeting
        if not meeting_id and client_id:
            meetings = self.memory.get_meetings_by_client(client_id, limit=5)
            completed_meetings = [m for m in meetings if m.status == "completed"]
            if completed_meetings:
                meeting_id = completed_meetings[0].id
        
        # Get meeting from database
        if meeting_id:
            meeting = self.memory.get_meeting_by_id(meeting_id)
            if meeting:
                client_name = None
                if meeting.client_id:
                    client = self.memory.get_client_by_id(meeting.client_id)
                    if client:
                        client_name = client.name
                
                # Get decisions
                db_decisions = self.memory.get_decisions_by_meeting_id(meeting_id)
                decisions = [{"description": d.description, "context": d.context} for d in db_decisions]
                
                result["structured_data"] = {
                    "meeting_summary": meeting.summary,
                    "transcript": meeting.transcript,
                    "meeting_title": meeting.title,
                    "client_name": client_name,
                    "action_items": [],
                    "decisions": decisions
                }
        
        return result
    
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
        try:
            if intent == "meeting_brief":
                return await self._execute_meeting_brief(integration_data)
            
            elif intent == "summarization":
                return await self._execute_summarization(
                    integration_data, user_id, client_id
                )
            
            elif intent == "followup":
                return await self._execute_followup(integration_data)
            
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
        integration_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute meeting brief tool."""
        structured_data = integration_data.get("structured_data", {})
        
        # Check if we have enough context
        if not structured_data.get("client_name"):
            return None
        
        # Call tool with structured input
        result = await self.meeting_brief_tool.generate_brief(**structured_data)
        
        return {
            "tool_name": "meeting_brief",
            "result": result
        }
    
    async def _execute_summarization(
        self,
        integration_data: Dict[str, Any],
        user_id: Optional[int],
        client_id: Optional[int]
    ) -> Dict[str, Any]:
        """Execute summarization tool."""
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
        result = await self.summarization_tool.summarize_meeting(**structured_data)
        
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
        
        return {
            "tool_name": "summarization",
            "result": result
        }
    
    async def _execute_followup(
        self,
        integration_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute follow-up tool."""
        structured_data = integration_data.get("structured_data", {})
        
        if not structured_data.get("meeting_summary"):
            return {
                "tool_name": "followup",
                "error": "No meeting summary available for follow-up."
            }
        
        # Call tool with structured input
        result = await self.followup_tool.generate_followup(**structured_data)
        
        return {
            "tool_name": "followup",
            "result": result
        }
