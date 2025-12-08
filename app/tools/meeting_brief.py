"""Meeting brief tool for pre-meeting preparation."""

from typing import Dict, Any, Optional
from app.llm.gemini_client import GeminiClient
from app.memory.repo import MemoryRepository
from app.integrations.zoom_client import ZoomClient


class MeetingBriefTool:
    """Tool for generating meeting briefs."""
    
    def __init__(self, llm_client: GeminiClient, memory_repo: MemoryRepository):
        self.llm = llm_client
        self.memory = memory_repo
    
    async def generate_brief(
        self,
        client_name: str = None,
        meeting_title: str = None,
        zoom_meeting_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate a meeting brief.
        
        Args:
            client_name: Client name
            meeting_title: Meeting title
            zoom_meeting_id: Optional Zoom meeting ID to fetch previous meeting transcript for context
        """
        # If zoom_meeting_id provided, could fetch previous meeting transcript for context
        previous_transcript = None
        if zoom_meeting_id:
            try:
                zoom_client = ZoomClient()
                
                # Try direct transcript endpoint first
                print(f"   🔍 Fetching previous meeting transcript for context...")
                previous_transcript = await zoom_client.get_meeting_transcript_direct(zoom_meeting_id)
                
                # If direct endpoint fails, try UUID-based approach
                if not previous_transcript:
                    print(f"   ⚠️ Direct endpoint failed, trying UUID-based approach...")
                    # Get UUID from meeting ID (most recent instance)
                    meeting_uuid = await zoom_client.get_meeting_uuid_from_id(
                        meeting_id=zoom_meeting_id,
                        expected_date=None  # Get most recent
                    )
                    
                    if meeting_uuid:
                        print(f"   ✅ Found UUID, getting transcript...")
                        previous_transcript = await zoom_client.get_transcript_by_uuid(meeting_uuid)
                        if previous_transcript:
                            print(f"   ✅ Retrieved transcript using UUID-based method (same as test_get_transcript_by_uuid.py)")
                
                # Final fallback: recordings-based approach
                if not previous_transcript:
                    print(f"   ⚠️ UUID approach failed, trying recordings-based fallback...")
                    previous_transcript = await zoom_client.get_meeting_transcript_from_recordings(
                        meeting_id=zoom_meeting_id,
                        expected_date=None  # Use most recent recording
                    )
                    if previous_transcript:
                        print(f"   ✅ Retrieved transcript using recordings-based method")
                
            except Exception as e:
                print(f"⚠️ Could not fetch previous meeting transcript for brief: {e}")
                import traceback
                print(traceback.format_exc())
        
        # Placeholder implementation - would use client data, previous meetings, etc.
        return {
            "brief": "Meeting brief would be generated here.",
            "client_name": client_name,
            "meeting_title": meeting_title
        }

