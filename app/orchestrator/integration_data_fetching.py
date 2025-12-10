"""Integration data fetching module - handles fetching data from external integrations."""

from typing import Dict, Any, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from app.memory.repo import MemoryRepository
from app.memory.schemas import MeetingCreate
from app.integrations.google_calendar_client import (
    get_calendar_event_by_id,
    extract_zoom_meeting_id_from_event
)
from app.integrations.zoom_client import (
    get_zoom_transcript_by_meeting_id,
    get_zoom_transcript_by_uuid,
    get_zoom_meeting_uuid
)
from app.utils.date_utils import (
    extract_event_datetime,
    parse_iso_datetime,
    format_datetime_display
)
from app.utils.calendar_utils import extract_attendees
from app.orchestrator.client_detection.client_inference import ClientInferenceService
from app.llm.gemini_client import GeminiClient


class IntegrationDataFetcher:
    """Handles fetching data from external integrations (Zoom, Google Calendar, etc.)."""
    
    def __init__(self, db: Session, memory: MemoryRepository):
        self.db = db
        self.memory = memory
    
    async def fetch_zoom_transcript(
        self,
        zoom_meeting_id: str,
        expected_date: Optional[datetime] = None
    ) -> Optional[str]:
        """
        Fetch transcript from Zoom for a meeting ID.
        
        Args:
            zoom_meeting_id: Zoom meeting ID
            expected_date: Optional expected date/time for matching
        
        Returns:
            Transcript text or None if not found
        """
        try:
            # Try UUID-based approach first
            meeting_uuid = await get_zoom_meeting_uuid(zoom_meeting_id, expected_date)
            
            if meeting_uuid:
                transcript = await get_zoom_transcript_by_uuid(meeting_uuid)
                if transcript:
                    return transcript
            
            # Fallback: Direct approach
            transcript = await get_zoom_transcript_by_meeting_id(zoom_meeting_id, expected_date)
            return transcript
            
        except Exception as e:
            print(f"Error fetching Zoom transcript: {e}")
            return None
    
    async def process_calendar_event_for_summarization(
        self,
        calendar_event: Dict[str, Any],
        user_id: Optional[int],
        client_id: Optional[int]
    ) -> Dict[str, Any]:
        """
        Process a calendar event: extract Zoom ID, fetch transcript, create meeting.
        
        Returns structured data for summarization tool.
        """
        event_title = calendar_event.get('summary', 'Untitled')
        event_id = calendar_event.get('id', 'Unknown')
        
        # Parse calendar event date/time
        event_date = extract_event_datetime(calendar_event)
        if not event_date:
            return {"error": "Calendar event has no valid start time"}
        
        # Get start_time_str for later use in scheduled_time parsing
        event_start = calendar_event.get('start', {})
        start_time_str = event_start.get('dateTime') or event_start.get('date')
        
        # Extract Zoom meeting ID
        try:
            zoom_meeting_id = extract_zoom_meeting_id_from_event(calendar_event)
        except Exception as e:
            print(f"Error extracting Zoom meeting ID: {e}")
            zoom_meeting_id = None
        
        # Extract attendees (for display as string and for database as list)
        attendees_str = extract_attendees(calendar_event)
        # Convert attendees string to list for MeetingCreate schema
        attendees_list = None
        if attendees_str and attendees_str != "Not specified":
            attendees_list = [name.strip() for name in attendees_str.split(",") if name.strip()]
        
        formatted_date = format_datetime_display(event_date)
        
        # If no Zoom ID, return calendar-only data
        if not zoom_meeting_id:
            return {
                "meeting_title": event_title,
                "meeting_date": formatted_date,
                "recording_date": None,
                "attendees": attendees_str,
                "transcript": None,
                "has_transcript": False,
                "meeting_id": None
            }
        
        # Fetch transcript from Zoom
        transcript = await self.fetch_zoom_transcript(zoom_meeting_id, event_date)
        
        # VALIDATION B2: Validate transcript and correct has_transcript flag
        if transcript is not None:
            # 1: dict always indicates an error-like payload
            if isinstance(transcript, dict):
                transcript = None
            # 2: non-string transcripts (numbers, lists, booleans)
            elif not isinstance(transcript, str):
                transcript = None
            # 3: empty or whitespace-only strings
            elif transcript == "" or transcript.strip() == "":
                transcript = None
            # 4: error-like string content
            elif transcript.lower().startswith("error"):
                transcript = None
        
        # Set has_transcript based on validated transcript
        has_transcript = transcript is not None
        
        # Create meeting in database (even if no transcript found)
        # This allows summaries and decisions to be saved later
        meeting_id = None
        if zoom_meeting_id:
            try:
                # Parse the datetime and remove timezone for database storage
                scheduled_time_dt = parse_iso_datetime(start_time_str) if start_time_str else None
                if scheduled_time_dt:
                    scheduled_time = scheduled_time_dt.replace(tzinfo=None)
                else:
                    scheduled_time = datetime.utcnow()
            except (ValueError, AttributeError):
                scheduled_time = datetime.utcnow()
            
            # Infer client_id if not provided
            if client_id is None:
                client_inference = ClientInferenceService(self.memory, GeminiClient())
                client_id = client_inference.infer_client_id(
                    meeting_title=event_title,
                    attendees=attendees_list,
                    user_id=user_id
                )
            
            meeting_data = MeetingCreate(
                user_id=user_id or 1,
                client_id=client_id,
                calendar_event_id=event_id,
                zoom_meeting_id=zoom_meeting_id,
                title=event_title,
                scheduled_time=scheduled_time,
                transcript=transcript,  # Can be None if not found
                status="completed",
                attendees=attendees_list  # List format for database
            )
            
            db_meeting = self.memory.create_meeting(meeting_data)
            meeting_id = db_meeting.id
        
        return {
            "meeting_title": event_title,
            "meeting_date": formatted_date,
            "recording_date": formatted_date,  # Use event date as recording date
            "attendees": attendees_str,
            "transcript": transcript,
            "has_transcript": has_transcript,
            "meeting_id": meeting_id
        }
    
    def get_calendar_event_details(
        self,
        calendar_event_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get calendar event details by ID.
        
        Args:
            calendar_event_id: Google Calendar event ID
        
        Returns:
            Event dictionary with parsed details or None
        """
        try:
            event = get_calendar_event_by_id(calendar_event_id)
            if not event:
                return None
            
            # Parse and format date
            dt = extract_event_datetime(event)
            meeting_date = format_datetime_display(dt) if dt else None
            
            # Get attendees
            attendees = extract_attendees(event)
            
            return {
                "meeting_title": event.get('summary'),
                "meeting_date": meeting_date,
                "attendees": attendees
            }
        except Exception as e:
            print(f"Error fetching calendar event details: {e}")
            return None

