"""Follow-up email generation tool."""

from typing import Dict, Any, Optional
from app.llm.gemini_client import GeminiClient
from app.memory.repo import MemoryRepository
from app.integrations.zoom_client import ZoomClient


class FollowUpTool:
    """Tool for generating follow-up emails."""
    
    def __init__(self, llm_client: GeminiClient, memory_repo: MemoryRepository):
        self.llm = llm_client
        self.memory = memory_repo
    
    async def generate_followup(
        self,
        meeting_id: int = None,
        client_id: int = None,
        zoom_meeting_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate a follow-up email.
        
        Args:
            meeting_id: Database meeting ID
            client_id: Client ID
            zoom_meeting_id: Optional Zoom meeting ID to fetch transcript if needed
        """
        # Get meeting from database if meeting_id provided
        meeting = None
        transcript = None
        
        if meeting_id:
            meeting = self.memory.get_meeting_by_id(meeting_id)
            if meeting:
                transcript = meeting.transcript
        
        # If no transcript and zoom_meeting_id provided, try to fetch it
        if not transcript and zoom_meeting_id:
            try:
                zoom_client = ZoomClient()
                
                # Try direct transcript endpoint first
                print(f"   🔍 Fetching transcript for follow-up email...")
                transcript = await zoom_client.get_meeting_transcript_direct(zoom_meeting_id)
                
                # If direct endpoint fails, try UUID-based approach
                if not transcript:
                    print(f"   ⚠️ Direct endpoint failed, trying UUID-based approach...")
                    # Get UUID from meeting ID (most recent instance)
                    meeting_uuid = await zoom_client.get_meeting_uuid_from_id(
                        meeting_id=zoom_meeting_id,
                        expected_date=None  # Get most recent
                    )
                    
                    if meeting_uuid:
                        print(f"   ✅ Found UUID, getting transcript...")
                        transcript = await zoom_client.get_transcript_by_uuid(meeting_uuid)
                        if transcript:
                            print(f"   ✅ Retrieved transcript using UUID-based method (same as test_get_transcript_by_uuid.py)")
                
                # Final fallback: recordings-based approach
                if not transcript:
                    print(f"   ⚠️ UUID approach failed, trying recordings-based fallback...")
                    transcript = await zoom_client.get_meeting_transcript_from_recordings(
                        meeting_id=zoom_meeting_id,
                        expected_date=None  # Use most recent recording
                    )
                    if transcript:
                        print(f"   ✅ Retrieved transcript using recordings-based method")
                
            except Exception as e:
                print(f"⚠️ Could not fetch transcript for follow-up: {e}")
                import traceback
                print(traceback.format_exc())
        
        # Placeholder implementation - would use transcript and meeting data to generate email
        return {
            "subject": "Follow-up email subject",
            "body": "Follow-up email body would be generated here."
        }

