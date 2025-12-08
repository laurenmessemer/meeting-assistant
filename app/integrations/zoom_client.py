"""Zoom API client."""

import httpx
import re
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone, timedelta
import urllib.parse
from app.config import settings
import base64
import json


class ZoomClient:
    """Client for interacting with Zoom API."""
    
    def __init__(self):
        print(f"      [ZoomClient] Initializing ZoomClient...")
        self.account_id = settings.zoom_account_id
        self.client_id = settings.zoom_client_id
        self.client_secret = settings.zoom_client_secret
        self.base_url = "https://api.zoom.us/v2"
        
        print(f"      [ZoomClient] Configuration:")
        print(f"      [ZoomClient]   Account ID: {self.account_id[:10]}..." if self.account_id else "      [ZoomClient]   Account ID: None")
        print(f"      [ZoomClient]   Client ID: {self.client_id[:10]}..." if self.client_id else "      [ZoomClient]   Client ID: None")
        print(f"      [ZoomClient]   Client Secret: {'***' if self.client_secret else 'None'}")
        print(f"      [ZoomClient]   Base URL: {self.base_url}")
        
        try:
            print(f"      [ZoomClient] Getting access token...")
            self.access_token = self._get_access_token()
            print(f"      [ZoomClient] ✅ Access token retrieved: {self.access_token[:20]}...")
        except Exception as e:
            print(f"      [ZoomClient] ❌ ERROR: Failed to get access token: {e}")
            import traceback
            print(f"      [ZoomClient] Traceback: {traceback.format_exc()}")
            raise
    
    def _get_access_token(self) -> str:
        """Get Zoom access token using Server-to-Server OAuth."""
        try:
            auth_string = f"{self.client_id}:{self.client_secret}"
            encoded_auth = base64.b64encode(auth_string.encode()).decode()
            
            url = f"https://zoom.us/oauth/token?grant_type=account_credentials&account_id={self.account_id}"
            headers = {
                "Authorization": f"Basic {encoded_auth}",
                "Content-Type": "application/x-www-form-urlencoded"
            }
            
            print(f"      [ZoomClient]   OAuth request URL: {url}")
            print(f"      [ZoomClient]   Making OAuth token request...")
            
            response = httpx.post(url, headers=headers, timeout=30.0)
            
            print(f"      [ZoomClient]   OAuth response status: {response.status_code}")
            
            if response.status_code != 200:
                error_text = response.text[:500]
                print(f"      [ZoomClient]   ❌ OAuth failed: {error_text}")
                raise Exception(f"Failed to get access token: {response.status_code} - {error_text}")
            
            token_data = response.json()
            access_token = token_data.get("access_token")
            
            if not access_token:
                raise Exception("No access token in OAuth response")
            
            print(f"      [ZoomClient]   ✅ Access token retrieved successfully")
            return access_token
            
        except Exception as e:
            print(f"      [ZoomClient]   ❌ ERROR getting access token: {e}")
            raise
    
    def _get_headers(self) -> Dict[str, str]:
        """Get standard headers for API requests."""
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
    
    async def get_all_meeting_uuids(
        self,
        meeting_id: str,
        expected_date: Optional["datetime"] = None
    ) -> List[tuple]:
        """
        Get all UUIDs for a meeting ID, sorted by relevance.
        Returns list of (uuid, datetime, time_diff) tuples.
        
        Args:
            meeting_id: Numeric Zoom meeting ID
            expected_date: Optional expected meeting date/time (will be normalized to UTC).
                          If provided, UUIDs are sorted by time difference.
        
        Returns:
            List of (uuid, datetime, time_diff) tuples, sorted by relevance
        """
        # Normalize expected_date to UTC if provided
        if expected_date:
            if expected_date.tzinfo is None:
                expected_date = expected_date.replace(tzinfo=timezone.utc)
            else:
                expected_date = expected_date.astimezone(timezone.utc)
        
        # Remove spaces from meeting_id
        meeting_id = meeting_id.replace(" ", "").strip()
        
        uuid_list = []
        
        try:
            url = f"{self.base_url}/past_meetings/{meeting_id}/instances"
            response = httpx.get(url, headers=self._get_headers(), timeout=30.0)
            
            if response.status_code == 200:
                data = response.json()
                instances = data.get("meetings", [])
                
                for instance in instances:
                    instance_uuid = instance.get("uuid", "")
                    instance_start_time = instance.get("start_time", "")
                    
                    if not instance_start_time or not instance_uuid:
                        continue
                    
                    try:
                        # Parse and normalize instance date to UTC
                        if 'Z' in instance_start_time:
                            instance_dt = datetime.fromisoformat(instance_start_time.replace('Z', '+00:00'))
                        else:
                            instance_dt = datetime.fromisoformat(instance_start_time)
                        
                        if instance_dt.tzinfo is None:
                            instance_dt = instance_dt.replace(tzinfo=timezone.utc)
                        else:
                            instance_dt = instance_dt.astimezone(timezone.utc)
                        
                        # Calculate time difference if expected_date provided
                        time_diff = None
                        if expected_date:
                            time_diff = abs((instance_dt - expected_date).total_seconds())
                        
                        uuid_list.append((instance_uuid, instance_dt, time_diff))
                    except (ValueError, AttributeError):
                        continue
                
                # Sort by time difference if expected_date provided, otherwise by date (most recent first)
                if expected_date:
                    uuid_list.sort(key=lambda x: x[2] if x[2] is not None else float('inf'))
                else:
                    uuid_list.sort(key=lambda x: x[1], reverse=True)
                
                return uuid_list
        
        except Exception as e:
            print(f"      [ZoomClient] ❌ Error fetching meeting instances: {e}")
        
        return uuid_list
    
    async def get_meeting_uuid_from_id(
        self,
        meeting_id: str,
        expected_date: Optional["datetime"] = None
    ) -> Optional[str]:
        """
        Get the UUID for a specific meeting instance by matching date.
        If expected_date is None, returns the most recent instance.
        
        Args:
            meeting_id: Numeric Zoom meeting ID
            expected_date: Optional expected meeting date/time (will be normalized to UTC).
                          If None, returns most recent instance.
        
        Returns:
            Meeting UUID for the matching instance, or None if not found
        """
        # Normalize expected_date to UTC if provided
        if expected_date:
            if expected_date.tzinfo is None:
                expected_date = expected_date.replace(tzinfo=timezone.utc)
                print(f"      [ZoomClient] ⚠️ expected_date was timezone-naive, assumed UTC")
            else:
                expected_date = expected_date.astimezone(timezone.utc)
                print(f"      [ZoomClient] ✅ expected_date normalized to UTC: {expected_date}")
        else:
            print(f"      [ZoomClient] No expected_date provided, will return most recent instance")
        
        # Remove spaces from meeting_id
        meeting_id = meeting_id.replace(" ", "").strip()
        
        try:
            # Get all past meeting instances for this meeting ID
            url = f"{self.base_url}/past_meetings/{meeting_id}/instances"
            print(f"      [ZoomClient] Fetching meeting instances: {url}")
            
            response = httpx.get(url, headers=self._get_headers(), timeout=30.0)
            
            if response.status_code == 200:
                data = response.json()
                instances = data.get("meetings", [])
                print(f"      [ZoomClient] Found {len(instances)} meeting instance(s)")
                
                # Find the instance that matches the expected date, or most recent if no date provided
                best_match = None
                min_time_diff = float('inf')
                most_recent = None
                most_recent_dt = None
                
                for instance in instances:
                    instance_uuid = instance.get("uuid", "")
                    instance_start_time = instance.get("start_time", "")
                    
                    if not instance_start_time:
                        continue
                    
                    try:
                        # Parse and normalize instance date to UTC
                        if 'Z' in instance_start_time:
                            instance_dt = datetime.fromisoformat(instance_start_time.replace('Z', '+00:00'))
                        else:
                            instance_dt = datetime.fromisoformat(instance_start_time)
                        
                        # Normalize to UTC
                        if instance_dt.tzinfo is None:
                            instance_dt = instance_dt.replace(tzinfo=timezone.utc)
                        else:
                            instance_dt = instance_dt.astimezone(timezone.utc)
                        
                        # Track most recent instance
                        if most_recent_dt is None or instance_dt > most_recent_dt:
                            most_recent_dt = instance_dt
                            most_recent = instance_uuid
                        
                        # If expected_date provided, calculate time difference
                        if expected_date:
                            time_diff = abs((instance_dt - expected_date).total_seconds())
                            print(f"      [ZoomClient] Instance UUID: {instance_uuid[:20]}..., Start: {instance_dt}, Diff: {time_diff/60:.1f} min")
                            
                            # Keep track of closest match
                            if time_diff < min_time_diff:
                                min_time_diff = time_diff
                                best_match = (instance_uuid, instance_dt)
                        else:
                            print(f"      [ZoomClient] Instance UUID: {instance_uuid[:20]}..., Start: {instance_dt}")
                    
                    except (ValueError, AttributeError) as e:
                        print(f"      [ZoomClient] Error parsing instance date: {e}")
                        continue
                
                # If expected_date provided, return UUID if match is within ±2 days
                if expected_date:
                    # Convert time_diff from seconds to days
                    time_diff_days = min_time_diff / (24 * 3600) if best_match else float('inf')
                    
                    if best_match and time_diff_days <= 2:  # ±2 days
                        uuid, matched_dt = best_match
                        print(f"      [ZoomClient] ✅ Found matching UUID: {uuid[:20]}... (diff: {time_diff_days:.2f} days)")
                        print(f"      [ZoomClient]   Full UUID: {uuid}")
                        return uuid
                    elif best_match:
                        print(f"      [ZoomClient] ⚠️ Closest match is {time_diff_days:.2f} days away (exceeds ±2 day tolerance)")
                        print(f"      [ZoomClient]   ⚠️ However, trying this UUID anyway as fallback...")
                        uuid, matched_dt = best_match
                        return uuid  # Return it anyway as a fallback
                    else:
                        print(f"      [ZoomClient] ❌ No matching instance found within ±2 days")
                    return None
                else:
                    # No expected_date - return most recent instance
                    if most_recent:
                        print(f"      [ZoomClient] ✅ Returning most recent UUID: {most_recent[:20]}... (Start: {most_recent_dt})")
                        return most_recent
                    else:
                        print(f"      [ZoomClient] ❌ No instances found")
                        return None
            
            elif response.status_code == 404:
                print(f"      [ZoomClient] ⚠️ Meeting {meeting_id} not found or has no past instances")
            else:
                print(f"      [ZoomClient] ⚠️ API returned {response.status_code}: {response.text[:200]}")
        
        except Exception as e:
            print(f"      [ZoomClient] ❌ Error fetching meeting instances: {e}")
        
        return None
    
    async def get_transcript_by_uuid(self, meeting_uuid: str) -> Optional[str]:
        """
        Get transcript by UUID - matches the logic from test_get_transcript_by_uuid.py.
        This is the proven method that works.
        
        Args:
            meeting_uuid: Meeting UUID (e.g., "ARNpil5TSvSOhMAQC0UbXA==")
        
        Returns:
            Transcript text (parsed from VTT) or None
        """
        print(f"      [ZoomClient] 🔍 Getting transcript by UUID: {meeting_uuid[:30]}...")
        print(f"      [ZoomClient]   Full UUID: {meeting_uuid}")
        
        if not meeting_uuid:
            print(f"      [ZoomClient]   ❌ ERROR: UUID is empty or None")
            return None
        
        if not self.access_token:
            print(f"      [ZoomClient]   ❌ ERROR: No access token available")
            return None
        
        try:
            # IMPORTANT: UUIDs can contain special characters like / and = that break URL paths
            # UUIDs like "5Qm9bzXlS02m//xxanLZPQ==" have // which is interpreted as path separator
            # We MUST URL encode the UUID for the path, but httpx might do this automatically
            # However, we need to be careful - some UUIDs work without encoding, some need it
            
            # Try URL-encoded first (safest for UUIDs with special chars)
            encoded_uuid = urllib.parse.quote(meeting_uuid, safe='')
            url_encoded = f"{self.base_url}/meetings/{encoded_uuid}/recordings"
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }
            
            print(f"      [ZoomClient]   Original UUID: {meeting_uuid}")
            print(f"      [ZoomClient]   Encoded UUID: {encoded_uuid}")
            print(f"      [ZoomClient]   Trying encoded URL first: {url_encoded}")
            response = httpx.get(url_encoded, headers=headers, timeout=60.0)
            print(f"      [ZoomClient]   Response Status (encoded): {response.status_code}")
            
            # If 404 with encoded, try without encoding (for UUIDs that don't need it)
            if response.status_code == 404:
                print(f"      [ZoomClient]   ⚠️ Got 404 with encoded UUID, trying without encoding...")
                url_direct = f"{self.base_url}/meetings/{meeting_uuid}/recordings"
                print(f"      [ZoomClient]   Direct URL: {url_direct}")
                response = httpx.get(url_direct, headers=headers, timeout=60.0)
                print(f"      [ZoomClient]   Response Status (direct): {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                recording_files = data.get("recording_files", [])
                meeting_info = data.get("meeting_info", {})
                
                print(f"      [ZoomClient]   ✅ Found recordings")
                print(f"      [ZoomClient]   Meeting Topic: {meeting_info.get('topic', 'N/A')}")
                print(f"      [ZoomClient]   Recording Files: {len(recording_files)}")
                
                # Find transcript file (exact same logic as test file)
                for file in recording_files:
                    file_type = file.get("file_type", "").upper()
                    recording_type = file.get("recording_type", "").upper()
                    file_name = file.get("file_name", "").lower()
                    file_extension = file.get("file_extension", "").upper()
                    
                    print(f"      [ZoomClient]   File: {file.get('file_name', 'N/A')}")
                    print(f"      [ZoomClient]      Type: {file_type}, Recording Type: {recording_type}, Extension: {file_extension}")
                    
                    is_transcript = (
                        file_type == "TRANSCRIPT" or
                        recording_type == "AUDIO_TRANSCRIPT" or
                        file_extension == "VTT" or
                        (file_name and file_name.endswith(".vtt")) or
                        (file_name and "transcript" in file_name and "timeline" not in file_name)
                    )
                    
                    if is_transcript:
                        print(f"      [ZoomClient]      ✅ TRANSCRIPT FILE FOUND!")
                        download_url = file.get("download_url")
                        
                        if download_url:
                            print(f"      [ZoomClient]      Download URL: {download_url[:80]}...")
                            print(f"      [ZoomClient]   📥 Downloading transcript...")
                            
                            download_response = httpx.get(
                                download_url,
                                headers={"Authorization": f"Bearer {self.access_token}"},
                                timeout=120.0,
                                follow_redirects=True
                            )
                            
                            if download_response.status_code == 200:
                                transcript_text = download_response.text
                                print(f"      [ZoomClient]      ✅ Downloaded {len(transcript_text)} characters")
                                
                                # Parse VTT if needed (exact same as test file)
                                if file_extension == "VTT" or (file_name and file_name.endswith(".vtt")) or transcript_text.strip().startswith("WEBVTT"):
                                    print(f"      [ZoomClient]      🔧 Parsing VTT format...")
                                    transcript_text = self._parse_vtt(transcript_text)
                                    print(f"      [ZoomClient]      ✅ Parsed to {len(transcript_text)} characters")
                                
                                return transcript_text
                            else:
                                print(f"      [ZoomClient]      ❌ Download failed: {download_response.status_code}")
                                print(f"      [ZoomClient]      Response: {download_response.text[:500]}")
                
                print(f"      [ZoomClient]   ⚠️ No transcript file found in {len(recording_files)} file(s)")
                print(f"      [ZoomClient]   Available files:")
                for file in recording_files:
                    print(f"      [ZoomClient]      - {file.get('file_name', 'N/A')} ({file.get('file_type', 'N/A')})")
            else:
                print(f"      [ZoomClient]   ❌ Failed: {response.status_code}")
                try:
                    error = response.json()
                    print(f"      [ZoomClient]   Error: {error.get('message', 'N/A')}")
                except:
                    print(f"      [ZoomClient]   Response: {response.text[:500]}")
            
            return None
            
        except Exception as e:
            print(f"      [ZoomClient]   ❌ ERROR: {e}")
            import traceback
            print(f"      [ZoomClient]   Traceback: {traceback.format_exc()}")
            return None
    
    async def get_meeting_recordings(
        self,
        meeting_id: Optional[str] = None,
        meeting_uuid: Optional[str] = None,
        expected_date: Optional["datetime"] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Get recordings for a meeting using UUID matching only.
        
        Strategy: Get UUID from meeting ID + date if needed, then fetch recordings by UUID.
        
        Args:
            meeting_id: Numeric Zoom meeting ID (required if UUID not provided)
            meeting_uuid: Meeting UUID (preferred, most accurate)
            expected_date: Expected meeting date/time (required if UUID not provided, normalized to UTC)
        
        Returns:
            Dict with 'recording_files' and 'meeting_info', or None if not found
        """
        print(f"      [ZoomClient] ========================================")
        print(f"      [ZoomClient] get_meeting_recordings() called")
        print(f"      [ZoomClient] ========================================")
        print(f"      [ZoomClient] Input parameters:")
        print(f"      [ZoomClient]   meeting_id: '{meeting_id}' (type: {type(meeting_id).__name__})")
        print(f"      [ZoomClient]   meeting_uuid: '{meeting_uuid}'")
        print(f"      [ZoomClient]   expected_date: {expected_date} (type: {type(expected_date).__name__})")
        
        # Normalize expected_date to UTC if provided
        if expected_date:
            if expected_date.tzinfo is None:
                expected_date = expected_date.replace(tzinfo=timezone.utc)
                print(f"      [ZoomClient] ⚠️ expected_date was timezone-naive, assumed UTC")
            else:
                expected_date = expected_date.astimezone(timezone.utc)
                print(f"      [ZoomClient] ✅ expected_date normalized to UTC: {expected_date}")
        
        # STRATEGY: Search user recordings by meeting ID + date/time (PRIMARY METHOD)
        # This directly searches and returns recording data, no UUID lookup needed
        if not meeting_uuid and meeting_id and expected_date:
            print(f"      [ZoomClient] Searching user recordings by meeting ID + date/time...")
            print(f"      [ZoomClient]   Meeting ID: {meeting_id}")
            print(f"      [ZoomClient]   Expected date (UTC): {expected_date}")
            
            # Search user recordings for matching meeting ID and date - returns recording data directly
            # Use ±2 day window to find recordings
            recording_data = await self._find_recording_by_meeting_id_and_date(
                meeting_id, 
                expected_date,
                tolerance_days=2
            )
            
            if recording_data:
                print(f"      [ZoomClient] ✅ Found recording via direct search")
                return recording_data
            else:
                print(f"      [ZoomClient] ⚠️ Direct search failed, trying UUID lookup...")
        
        # If we don't have a UUID yet, try to get it from meeting_id
        if not meeting_uuid and meeting_id:
            print(f"      [ZoomClient] Getting UUID from meeting ID...")
            uuid_from_instances = await self.get_meeting_uuid_from_id(meeting_id, expected_date)
            if uuid_from_instances:
                meeting_uuid = uuid_from_instances
                print(f"      [ZoomClient] ✅ Got UUID: {meeting_uuid[:30]}...")
            else:
                print(f"      [ZoomClient] ⚠️ Could not get UUID from meeting ID")
        
        # If we still don't have a UUID, we can't proceed
        if not meeting_uuid:
            print(f"      [ZoomClient] ❌ Could not fetch recordings: No UUID available")
            print(f"      [ZoomClient]   Need either:")
            print(f"      [ZoomClient]     - meeting_uuid parameter, OR")
            print(f"      [ZoomClient]     - meeting_id + expected_date to lookup UUID")
            return None
        
        # Now get recordings by UUID (exact same as test file)
        print(f"      [ZoomClient] Getting recordings by UUID: {meeting_uuid[:30]}...")
        url = f"{self.base_url}/meetings/{meeting_uuid}/recordings"
        headers = self._get_headers()
        
        print(f"      [ZoomClient]   Request URL: {url}")
        try:
            response = httpx.get(url, headers=headers, timeout=60.0)
            print(f"      [ZoomClient]   Response Status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                print(f"      [ZoomClient]   ✅ Successfully retrieved recordings")
                return data
            else:
                print(f"      [ZoomClient]   ❌ API returned {response.status_code}")
                print(f"      [ZoomClient]   Response: {response.text[:500]}")
                return None
                
        except Exception as e:
            print(f"      [ZoomClient]   ❌ Error: {e}")
            import traceback
            print(f"      [ZoomClient]   Traceback: {traceback.format_exc()}")
            return None
    
    async def _find_recording_by_meeting_id_and_date(
        self,
        meeting_id: str,
        expected_date: datetime,
        tolerance_days: int = 2
    ) -> Optional[Dict[str, Any]]:
        """
        Search user recordings by meeting ID and date/time.
        Returns recording data directly if found.
        
        Args:
            meeting_id: Normalized meeting ID (no spaces)
            expected_date: Expected meeting date/time (UTC)
            tolerance_days: Time tolerance in days (default: ±2 days)
        
        Returns:
            Recording data dict or None
        """
        print(f"      [ZoomClient] Searching /users/me/recordings for meeting ID {meeting_id}")
        print(f"      [ZoomClient]   Expected date: {expected_date.date()}")
        print(f"      [ZoomClient]   Search window: ±{tolerance_days} days")
        
        # Search within ±2 days (or specified tolerance)
        search_start = (expected_date - timedelta(days=tolerance_days)).date()
        search_end = (expected_date + timedelta(days=tolerance_days)).date()
        
        url = f"{self.base_url}/users/me/recordings"
        params = {
            "from": search_start.strftime("%Y-%m-%d"),
            "to": search_end.strftime("%Y-%m-%d"),
            "page_size": 30
        }
        
        headers = self._get_headers()
        
        try:
            response = httpx.get(url, headers=headers, params=params, timeout=60.0)
            
            if response.status_code == 200:
                data = response.json()
                meetings = data.get("meetings", [])
                print(f"      [ZoomClient] Found {len(meetings)} recording(s) in date range ({search_start} to {search_end})")
                
                # Find matching meeting by ID and time (within ±2 day window)
                best_match = None
                min_time_diff = float('inf')
                
                for meeting in meetings:
                    meeting_info = meeting.get("meeting_info", {})
                    meeting_id_from_recording = meeting_info.get("meeting_id")
                    
                    # Normalize meeting IDs for comparison
                    meeting_id_normalized = str(meeting_id).replace(" ", "").replace("-", "")
                    recording_id_normalized = str(meeting_id_from_recording).replace(" ", "").replace("-", "") if meeting_id_from_recording else ""
                    
                    if recording_id_normalized == meeting_id_normalized:
                        start_time_str = meeting_info.get("start_time", "")
                        if start_time_str:
                            try:
                                if 'Z' in start_time_str:
                                    recording_dt = datetime.fromisoformat(start_time_str.replace('Z', '+00:00'))
                                else:
                                    recording_dt = datetime.fromisoformat(start_time_str)
                                
                                if recording_dt.tzinfo is None:
                                    recording_dt = recording_dt.replace(tzinfo=timezone.utc)
                                else:
                                    recording_dt = recording_dt.astimezone(timezone.utc)
                                
                                # Calculate time difference in days
                                time_diff_days = abs((recording_dt - expected_date).total_seconds()) / (24 * 3600)
                                
                                # Keep track of closest match within ±2 days
                                if time_diff_days <= tolerance_days and time_diff_days < min_time_diff:
                                    min_time_diff = time_diff_days
                                    best_match = meeting
                                    print(f"      [ZoomClient]   Found potential match (time diff: {time_diff_days:.2f} days)")
                            except (ValueError, AttributeError):
                                pass
                
                if best_match:
                    print(f"      [ZoomClient] ✅ Found matching recording (time diff: {min_time_diff:.2f} days)")
                    return best_match
                
                print(f"      [ZoomClient] ⚠️ No matching recording found")
            else:
                print(f"      [ZoomClient] ⚠️ /users/me/recordings returned {response.status_code}")
        except Exception as e:
            print(f"      [ZoomClient] ❌ Error searching recordings: {e}")
        
        return None
    
    async def get_meeting_transcript_from_recordings(
        self, 
        meeting_id: str,
        expected_date: Optional[datetime] = None
    ) -> Optional[str]:
        """
        Get transcript from meeting recordings by meeting ID.
        Uses UUID-based approach (same as test_get_transcript_by_uuid.py).
        
        This method:
        1. Gets UUID from meeting ID (using date if provided, or most recent)
        2. Calls get_transcript_by_uuid() which matches test_get_transcript_by_uuid.py exactly
        
        Args:
            meeting_id: Zoom meeting ID (can have spaces)
            expected_date: Optional expected date/time for matching
        
        Returns:
            Transcript text (parsed from VTT) or None
        """
        # Normalize meeting ID
        meeting_id_clean = meeting_id.replace(" ", "").strip()
        
        print(f"      [ZoomClient] Getting transcript for meeting ID: {meeting_id_clean}")
        print(f"      [ZoomClient] Using UUID-based approach (same as test_get_transcript_by_uuid.py)")
        
        # Step 1: Get UUID from meeting ID
        meeting_uuid = await self.get_meeting_uuid_from_id(
            meeting_id=meeting_id_clean,
            expected_date=expected_date
        )
        
        if not meeting_uuid:
            print(f"      [ZoomClient] ❌ Could not get UUID for meeting ID {meeting_id_clean}")
            return None
        
        # Step 2: Get transcript by UUID (exact same as test file)
        print(f"      [ZoomClient] ✅ Got UUID, now getting transcript using proven UUID method")
        return await self.get_transcript_by_uuid(meeting_uuid)
    
    async def get_meeting_transcript_direct(
        self,
        meeting_id: str
    ) -> Optional[str]:
        """
        Get transcript directly using the /meetings/{meeting_id}/transcript endpoint.
        This is the preferred method as it's simpler and more direct.
        
        Args:
            meeting_id: Zoom meeting ID (can have spaces like "850 9651 9957")
        
        Returns:
            Transcript text or None if not available
        """
        # Normalize meeting ID (remove spaces)
        meeting_id_clean = meeting_id.replace(" ", "").strip()
        
        print(f"      [ZoomClient] 🔍 Getting transcript directly for meeting ID: {meeting_id_clean}")
        
        try:
            # Step 1: Get transcript information
            url = f"{self.base_url}/meetings/{meeting_id_clean}/transcript"
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }
            
            print(f"      [ZoomClient]   Request URL: {url}")
            response = httpx.get(url, headers=headers, timeout=60.0)
            print(f"      [ZoomClient]   Response Status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                print(f"      [ZoomClient]   ✅ Transcript information retrieved")
                print(f"      [ZoomClient]   Meeting Topic: {data.get('meeting_topic', 'N/A')}")
                print(f"      [ZoomClient]   Meeting ID: {data.get('meeting_id', 'N/A')}")
                print(f"      [ZoomClient]   Can Download: {data.get('can_download', False)}")
                print(f"      [ZoomClient]   Full response keys: {list(data.keys())}")
                
                if data.get('can_download'):
                    download_url = data.get('download_url')
                    if download_url:
                        print(f"      [ZoomClient]   📥 Downloading transcript from URL...")
                        print(f"      [ZoomClient]   Download URL: {download_url[:100]}...")
                        
                        # Step 2: Download the transcript file
                        download_headers = {
                            "Authorization": f"Bearer {self.access_token}"
                        }
                        download_response = httpx.get(
                            download_url,
                            headers=download_headers,
                            timeout=120.0,
                            follow_redirects=True
                        )
                        
                        print(f"      [ZoomClient]   Download response status: {download_response.status_code}")
                        if download_response.status_code == 200:
                            transcript_text = download_response.text
                            print(f"      [ZoomClient]   📄 Downloaded {len(transcript_text)} characters")
                            
                            # Parse VTT if needed
                            if download_url.endswith('.vtt') or 'vtt' in download_url.lower():
                                print(f"      [ZoomClient]   🔧 Parsing VTT format...")
                                transcript_text = self._parse_vtt(transcript_text)
                                print(f"      [ZoomClient]   ✅ Parsed to {len(transcript_text)} characters of text")
                            
                            return transcript_text
                        else:
                            print(f"      [ZoomClient]   ❌ Download failed: {download_response.status_code}")
                            print(f"      [ZoomClient]   Response headers: {dict(download_response.headers)}")
                            print(f"      [ZoomClient]   Response: {download_response.text[:500]}")
                            return None
                    else:
                        print(f"      [ZoomClient]   ⚠️ No download URL in response")
                        print(f"      [ZoomClient]   Response data: {data}")
                        return None
                else:
                    restriction_reason = data.get('download_restriction_reason', 'N/A')
                    print(f"      [ZoomClient]   ⚠️ Cannot download transcript: {restriction_reason}")
                    print(f"      [ZoomClient]   Full response: {data}")
                    return None
            else:
                print(f"      [ZoomClient]   ❌ API returned {response.status_code}")
                print(f"      [ZoomClient]   Response headers: {dict(response.headers)}")
                print(f"      [ZoomClient]   Response body: {response.text[:1000]}")
                # Try to parse error details
                try:
                    error_data = response.json()
                    print(f"      [ZoomClient]   Error details: {error_data}")
                except:
                    pass
                return None
                
        except Exception as e:
            print(f"      [ZoomClient]   ❌ ERROR getting transcript: {e}")
            import traceback
            print(f"      [ZoomClient]   Traceback: {traceback.format_exc()}")
            return None
    
    async def _get_recordings_by_meeting_id_no_date(self, meeting_id: str) -> Optional[Dict[str, Any]]:
        """
        Get recordings by meeting ID without requiring a specific date.
        Searches all available recordings and returns the most recent match.
        
        Args:
            meeting_id: Normalized meeting ID (no spaces)
        
        Returns:
            Recording data dict or None
        """
        print(f"      [ZoomClient] Searching all recordings (last 90 days) for meeting ID {meeting_id}...")
        
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(days=90)
        
        url = f"{self.base_url}/users/me/recordings"
        params = {
            "from": start_time.strftime("%Y-%m-%d"),
            "to": end_time.strftime("%Y-%m-%d"),
            "page_size": 30
        }
        
        headers = self._get_headers()
        
        try:
            response = httpx.get(url, headers=headers, params=params, timeout=60.0)
            
            if response.status_code == 200:
                data = response.json()
                meetings = data.get("meetings", [])
                print(f"      [ZoomClient] Found {len(meetings)} total recording(s)")
                
                # Find most recent matching meeting
                matching_meetings = []
                for meeting in meetings:
                    meeting_info = meeting.get("meeting_info", {})
                    meeting_id_from_recording = meeting_info.get("meeting_id")
                    
                    # Normalize for comparison
                    meeting_id_normalized = str(meeting_id).replace(" ", "").replace("-", "")
                    recording_id_normalized = str(meeting_id_from_recording).replace(" ", "").replace("-", "") if meeting_id_from_recording else ""
                    
                    if recording_id_normalized == meeting_id_normalized:
                        matching_meetings.append(meeting)
                
                if matching_meetings:
                    # Sort by start_time (most recent first)
                    matching_meetings.sort(
                        key=lambda m: m.get("meeting_info", {}).get("start_time", ""),
                        reverse=True
                    )
                    print(f"      [ZoomClient] ✅ Found {len(matching_meetings)} matching recording(s), using most recent")
                    return matching_meetings[0]
                else:
                    print(f"      [ZoomClient] ❌ No recordings found for meeting ID {meeting_id}")
            else:
                print(f"      [ZoomClient] ⚠️ /users/me/recordings returned {response.status_code}")
        except Exception as e:
            print(f"      [ZoomClient] ❌ Error: {e}")
        
        return None
    
    async def _download_transcript_from_files(self, recording_files: list) -> Optional[str]:
        """
        Download and parse transcript from recording files.
        
        Args:
            recording_files: List of recording file dictionaries
        
        Returns:
            Parsed transcript text or None
        """
        import httpx
        
        print(f"      [ZoomClient]   Scanning {len(recording_files)} recording file(s) for transcript...")
        
        async with httpx.AsyncClient() as client:
            for file in recording_files:
                file_type = file.get("file_type", "").upper()
                recording_type = file.get("recording_type", "").upper()
                file_extension = file.get("file_extension", "").upper()
                file_name = file.get("file_name", "").lower()
                
                # Look for transcript files (exact same logic as test file)
                is_transcript = (
                    file_type == "TRANSCRIPT" or
                    recording_type == "AUDIO_TRANSCRIPT" or
                    file_extension == "VTT" or
                    (file_name and file_name.endswith(".vtt")) or
                    (file_name and "transcript" in file_name and "timeline" not in file_name)
                )
                
                if is_transcript:
                    print(f"      [ZoomClient]   ✅ Found transcript file: {file_name or 'N/A'}")
                    download_url = file.get("download_url")
                    
                    if not download_url:
                        print(f"      [ZoomClient]   ⚠️ No download URL found for transcript file")
                        continue
                    
                    try:
                        print(f"      [ZoomClient]   📥 Downloading transcript...")
                        headers = {
                            "Authorization": f"Bearer {self.access_token}"
                        }
                        response = await client.get(download_url, headers=headers, timeout=120.0, follow_redirects=True)
                        
                        if response.status_code == 200:
                            transcript_text = response.text
                            print(f"      [ZoomClient]   📄 Downloaded {len(transcript_text)} characters")
                            
                            # Parse VTT if needed (exact same as test file)
                            if file_extension == "VTT" or (file_name and file_name.endswith(".vtt")) or transcript_text.strip().startswith("WEBVTT"):
                                print(f"      [ZoomClient]   🔧 Parsing VTT format...")
                                transcript_text = self._parse_vtt(transcript_text)
                                print(f"      [ZoomClient]   ✅ Parsed to {len(transcript_text)} characters of text")
                            
                            return transcript_text
                        else:
                            print(f"      [ZoomClient]   ❌ Download failed: {response.status_code}")
                            continue
                            
                    except Exception as e:
                        print(f"      [ZoomClient]   ❌ Error downloading transcript: {str(e)}")
                        continue
        
        print(f"      [ZoomClient]   ❌ No transcript file found in {len(recording_files)} recording file(s)")
        return None
    
    def _parse_vtt(self, vtt_text: str) -> str:
        """Parse VTT file and extract plain text."""
        lines = vtt_text.split('\n')
        text_lines = []
        
        for line in lines:
            line = line.strip()
            # Skip VTT metadata lines
            if not line or line.startswith('WEBVTT') or line.startswith('NOTE') or '-->' in line:
                continue
            # Skip timestamps (format: 00:00:00.000 --> 00:00:00.000)
            if re.match(r'^\d{2}:\d{2}:\d{2}', line):
                continue
            text_lines.append(line)
        
        return '\n'.join(text_lines).strip()
