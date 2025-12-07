"""Zoom API client."""

import httpx
import base64
from typing import Optional, Dict, Any, List
from datetime import datetime
from app.config import settings


class ZoomClient:
    """Client for interacting with Zoom API."""
    
    def __init__(self):
        self.account_id = settings.zoom_account_id
        self.client_id = settings.zoom_client_id
        self.client_secret = settings.zoom_client_secret
        self.base_url = "https://api.zoom.us/v2"
        self.access_token = None
        self._get_access_token()
    
    def _get_access_token(self):
        """Get OAuth access token for Zoom API using Server-to-Server OAuth."""
        # For Server-to-Server OAuth
        url = "https://zoom.us/oauth/token"
        credentials = f"{self.client_id}:{self.client_secret}"
        encoded_credentials = base64.b64encode(credentials.encode()).decode()
        
        headers = {
            "Authorization": f"Basic {encoded_credentials}",
            "Content-Type": "application/x-www-form-urlencoded"
        }
        
        data = {
            "grant_type": "account_credentials",
            "account_id": self.account_id
        }
        
        try:
            response = httpx.post(url, headers=headers, data=data)
            response.raise_for_status()
            token_data = response.json()
            self.access_token = token_data.get("access_token")
        except Exception as e:
            raise Exception(f"Error getting Zoom access token: {str(e)}")
    
    def _get_headers(self) -> Dict[str, str]:
        """Get headers with authentication."""
        if not self.access_token:
            self._get_access_token()
        
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
    
    async def get_meetings(
        self, 
        user_id: str = "me",
        page_size: int = 30
    ) -> List[Dict[str, Any]]:
        """
        Get list of meetings for a user.
        
        Args:
            user_id: Zoom user ID (defaults to "me")
            page_size: Number of results per page
        
        Returns:
            List of meeting dictionaries
        """
        url = f"{self.base_url}/users/{user_id}/meetings"
        params = {"page_size": page_size}
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, headers=self._get_headers(), params=params)
                response.raise_for_status()
                data = response.json()
                return data.get("meetings", [])
            except httpx.HTTPError as e:
                raise Exception(f"Error fetching Zoom meetings: {str(e)}")
    
    async def get_meeting(self, meeting_id: str) -> Optional[Dict[str, Any]]:
        """
        Get details of a specific meeting.
        
        Args:
            meeting_id: Zoom meeting ID
        
        Returns:
            Meeting dictionary or None if not found
        """
        url = f"{self.base_url}/meetings/{meeting_id}"
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, headers=self._get_headers())
                response.raise_for_status()
                return response.json()
            except httpx.HTTPError as e:
                if response.status_code == 404:
                    return None
                raise Exception(f"Error fetching Zoom meeting: {str(e)}")
    
    async def get_meeting_recordings(self, meeting_id: str) -> List[Dict[str, Any]]:
        """
        Get recordings for a meeting.
        
        Args:
            meeting_id: Zoom meeting ID
        
        Returns:
            List of recording dictionaries
        """
        url = f"{self.base_url}/meetings/{meeting_id}/recordings"
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, headers=self._get_headers())
                response.raise_for_status()
                data = response.json()
                return data.get("recording_files", [])
            except httpx.HTTPError as e:
                if response.status_code == 404:
                    return []
                raise Exception(f"Error fetching Zoom recordings: {str(e)}")
    
    async def get_meeting_transcript(
        self, 
        meeting_id: str, 
        recording_id: str
    ) -> Optional[str]:
        """
        Get transcript for a meeting recording.
        
        Args:
            meeting_id: Zoom meeting ID
            recording_id: Recording ID
        
        Returns:
            Transcript text or None if not available
        """
        url = f"{self.base_url}/meetings/{meeting_id}/recordings/{recording_id}/transcript"
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, headers=self._get_headers())
                response.raise_for_status()
                data = response.json()
                
                # Extract transcript text from response
                # Zoom transcript format may vary
                if "transcript" in data:
                    return data["transcript"]
                elif "transcript_file" in data:
                    # If transcript is in a file, download it
                    transcript_url = data["transcript_file"].get("download_url")
                    if transcript_url:
                        transcript_response = await client.get(transcript_url)
                        return transcript_response.text
                
                return None
            except httpx.HTTPError as e:
                if response.status_code == 404:
                    return None
                raise Exception(f"Error fetching Zoom transcript: {str(e)}")
    
    async def search_meetings_by_time(
        self, 
        start_time: datetime, 
        end_time: datetime,
        user_id: str = "me"
    ) -> List[Dict[str, Any]]:
        """
        Search for meetings within a time range.
        
        Args:
            start_time: Start of time range
            end_time: End of time range
            user_id: Zoom user ID
        
        Returns:
            List of meeting dictionaries
        """
        all_meetings = await self.get_meetings(user_id=user_id, page_size=100)
        
        filtered_meetings = []
        for meeting in all_meetings:
            meeting_time_str = meeting.get("start_time")
            if meeting_time_str:
                try:
                    meeting_time = datetime.fromisoformat(meeting_time_str.replace('Z', '+00:00'))
                    if start_time <= meeting_time <= end_time:
                        filtered_meetings.append(meeting)
                except ValueError:
                    continue
        
        return filtered_meetings

