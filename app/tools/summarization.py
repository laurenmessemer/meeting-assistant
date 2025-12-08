"""Summarization tool for post-meeting analysis."""

from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from app.llm.gemini_client import GeminiClient
from app.llm.prompts import SUMMARIZATION_TOOL_PROMPT
from app.memory.repo import MemoryRepository
from app.memory.schemas import DecisionCreate, MeetingUpdate, MeetingCreate
from app.integrations.zoom_client import ZoomClient
from app.integrations.google_calendar_client import GoogleCalendarClient
import httpx
from datetime import datetime, timezone


class SummarizationTool:
    """Tool for summarizing meetings and extracting decisions/actions."""
    
    def __init__(
        self,
        llm_client: GeminiClient,
        memory_repo: MemoryRepository,
        db: Optional[Session] = None,
        calendar: Optional[GoogleCalendarClient] = None
    ):
        self.llm = llm_client
        self.memory = memory_repo
        self.db = db
        self.calendar = calendar
    
    async def summarize_meeting(
        self,
        meeting_id: Optional[int] = None,
        transcript: Optional[str] = None,
        zoom_meeting_id: Optional[str] = None,
        meeting_title: Optional[str] = None,
        meeting_date: Optional[str] = None,
        recording_date: Optional[str] = None,
        attendees: Optional[list] = None,
        calendar_event: Optional[Dict[str, Any]] = None,
        client_name: Optional[str] = None,
        user_id: Optional[int] = None,
        client_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Summarize a meeting and extract decisions/actions.
        
        Args:
            meeting_id: Optional database meeting ID
            transcript: Optional transcript text
            zoom_meeting_id: Optional Zoom meeting ID to fetch transcript
            meeting_title: Optional meeting title for display
            meeting_date: Optional calendar event date for display
            recording_date: Optional Zoom recording date for display
            attendees: Optional list of attendee names
            calendar_event: Optional calendar event dictionary to process
            client_name: Optional client name for context
            user_id: Optional user ID
            client_id: Optional client ID
        
        Returns:
            Dictionary with summary, decisions, and actions, or error dict
        """
        # If calendar_event is provided, process it first
        no_zoom_recording = False
        if calendar_event:
            result = await self._process_calendar_event(
                calendar_event, client_name, user_id, client_id
            )
            if result.get("error"):
                return result
            # Extract values from processed event
            meeting_id = result.get("meeting_id")
            transcript = result.get("transcript")
            meeting_title = result.get("meeting_title")
            meeting_date = result.get("meeting_date")
            recording_date = result.get("recording_date")
            attendees = result.get("attendees")
            no_zoom_recording = result.get("no_zoom_recording", False)
        
        # Get meeting from database if meeting_id provided
        meeting = None
        if meeting_id:
            print(f"\n🔍 DEBUG: Looking up meeting in database...")
            print(f"   📋 meeting_id: {meeting_id}")
            print(f"   🔗 memory_repo: {self.memory}")
            print(f"   🔗 db session: {getattr(self.memory, 'db', None)}")
            
            try:
                meeting = self.memory.get_meeting_by_id(meeting_id)
                print(f"   📊 Database query result: {meeting}")
                
                if meeting:
                    print(f"   ✅ Found meeting: ID={meeting.id}, Title='{meeting.title}', Transcript length={len(meeting.transcript) if meeting.transcript else 0}")
                else:
                    print(f"   ❌ Meeting {meeting_id} not found in database")
                    print(f"   🔍 Checking if meeting exists in database directly...")
                    
                    # Try direct database query as fallback
                    if self.db:
                        from app.memory.models import Meeting
                        direct_query = self.db.query(Meeting).filter(Meeting.id == meeting_id).first()
                        print(f"   📊 Direct query result: {direct_query}")
                        if direct_query:
                            print(f"   ✅ Found via direct query: ID={direct_query.id}, Title='{direct_query.title}'")
                            meeting = direct_query
                        else:
                            print(f"   ❌ Direct query also returned None")
                            # List all meetings in database for debugging
                            all_meetings = self.db.query(Meeting).all()
                            print(f"   📋 Total meetings in database: {len(all_meetings)}")
                            for m in all_meetings:
                                print(f"      - Meeting ID={m.id}, Title='{m.title}', Created={m.created_at}")
                    else:
                        print(f"   ⚠️ No db session available for direct query")
                    
                    if not meeting:
                        return {
                            "error": f"Meeting {meeting_id} not found"
                        }
            except Exception as e:
                import traceback
                print(f"   ❌ ERROR during meeting lookup: {str(e)}")
                print(f"   📋 Traceback: {traceback.format_exc()}")
                return {
                    "error": f"Error looking up meeting {meeting_id}: {str(e)}"
                }
        
        # Use provided transcript or get from meeting
        if not transcript and meeting:
            transcript = meeting.transcript
        
        # If still no transcript, return error
        if not transcript:
            title = meeting_title or (meeting.title if meeting and meeting.title else "this meeting")
            return {
                "error": (
                    f"No transcript available for {title}. "
                    "To summarize a meeting, you need a Zoom recording with transcript that matches the calendar event."
                )
            }
        
        # Use provided metadata or fall back to database values
        title = meeting_title or (meeting.title if meeting and meeting.title else "Untitled Meeting")
        date_str = meeting_date or "Unknown date"
        recording_date_str = recording_date or "N/A"
        attendees_display = ", ".join(attendees) if attendees else (meeting.attendees if meeting and meeting.attendees else "Not specified")
        
        # Generate structured summary using LLM
        if no_zoom_recording:
            # Generate summary without transcript - just calendar information
            prompt = f"""Create a meeting summary based on the available calendar information. Note that no Zoom recording is available for this meeting.

Meeting Information:
- Title: {title}
- Calendar Event Date: {date_str}
- Attendees: {attendees_display}

IMPORTANT: There is no Zoom recording or transcript available for this meeting. Please create a summary with the following EXACT structure and formatting:

# Meeting Header
{title}

## Date from calendar:
{date_str}

## Participants:
{attendees_display}

## Overview:
[Provide a brief 2-3 sentence summary based on the meeting title and attendees. Since no transcript is available, focus on what can be inferred from the meeting title and who was scheduled to attend.]

## Recording Status:
⚠️ No Zoom recording is available for this meeting. This summary is based solely on the calendar event information (title, date, and participants).

## Outline:
[Since no transcript is available, you cannot provide details about what was discussed. Instead, write: "No transcript available - unable to provide meeting outline."]

## Conclusion:
[Since no transcript is available, you cannot provide details about decisions or next steps. Instead, write: "No transcript available - unable to provide meeting conclusions."]

Format your response using the EXACT section headers shown above (with # and ## markdown formatting). Be clear, concise, and well-organized."""
        else:
            # Generate summary with transcript
            prompt = f"""Analyze the following meeting transcript and create a comprehensive, well-structured summary.

Meeting Information:
- Title: {title}
- Calendar Event Date: {date_str}
- Zoom Recording Date: {recording_date_str}
- Attendees: {attendees_display}

Meeting Transcript:
{transcript}

Please create a summary with the following EXACT structure and formatting:

# Meeting Header
{title}

## Date from calendar:
{date_str}

## Participants:
{attendees_display}

## Overview:
[Provide a brief 2-3 sentence summary of what the meeting was about, who attended, and the main purpose. Focus on the key objectives and outcomes.]

## Outline:
[Provide 2-3 sentences summarizing the major sections or topics discussed in the meeting. Write in complete sentences (not bullet points) that outline what was covered in each main section. Keep it succinct and focused on the key discussion areas.]

## Conclusion:
[Provide a summary of decisions made, next steps, and any important takeaways. Include any commitments, agreements, or follow-up requirements.]

Format your response using the EXACT section headers shown above (with # and ## markdown formatting). Be clear, concise, and well-organized."""
        
        summary_text = self.llm.generate(
            prompt,
            system_prompt=SUMMARIZATION_TOOL_PROMPT,
            temperature=0.3,  # Lower temperature for more factual summaries
        )
        
        # Extract structured data (decisions only) using LLM - skip if no transcript
        decisions = []
        if not no_zoom_recording:
            extraction_prompt = f"""Based on the following meeting summary, extract:
1. All decisions made (who decided what)

Meeting Summary:
{summary_text}

Respond in JSON format:
{{
    "decisions": [
        {{"description": "...", "context": "..."}}
    ]
}}"""
            
            structured_data = self.llm.generate_structured(
                extraction_prompt,
                response_format="JSON",
                temperature=0.2,
            )
            
            # Update meeting with summary (if meeting_id exists)
            if meeting_id:
                self.memory.update_meeting(
                    meeting_id,
                    MeetingUpdate(summary=summary_text, transcript=transcript)
                )
            
            # Store decisions
            if meeting and meeting.client_id:
                for decision_data in structured_data.get("decisions", []):
                    decision = self.memory.create_decision(
                        DecisionCreate(
                            meeting_id=meeting_id,
                            client_id=meeting.client_id,
                            description=decision_data.get("description", ""),
                            context=decision_data.get("context"),
                        )
                    )
                    decisions.append(decision)
        
        return {
            "summary": summary_text,
            "meeting_title": title,
            "meeting_date": date_str,
            "recording_date": recording_date_str,
            "attendees": attendees_display,
            "decisions": [
                {
                    "id": d.id,
                    "description": d.description,
                    "context": d.context,
                }
                for d in decisions
            ],
        }
    
    async def _process_calendar_event(
        self,
        calendar_event: Dict[str, Any],
        client_name: Optional[str],
        user_id: Optional[int],
        client_id: Optional[int]
    ) -> Dict[str, Any]:
        """Process a calendar event: extract Zoom ID, fetch transcript, create meeting."""
        event_title = calendar_event.get('summary', 'Untitled')
        event_id = calendar_event.get('id', 'Unknown')
        
        print(f"\n{'='*60}")
        print(f"📅 Processing calendar event: {event_title}")
        print(f"   Event ID: {event_id}")
        print(f"{'='*60}\n")
        
        # Parse calendar event date/time
        event_start = calendar_event.get('start', {})
        start_time_str = event_start.get('dateTime') or event_start.get('date')
        event_date = None
        if start_time_str:
            try:
                if 'T' in start_time_str:
                    event_date = datetime.fromisoformat(start_time_str.replace('Z', '+00:00'))
                else:
                    event_date = datetime.fromisoformat(start_time_str)
                if event_date.tzinfo is None:
                    event_date = event_date.replace(tzinfo=timezone.utc)
                else:
                    event_date = event_date.astimezone(timezone.utc)
                print(f"✅ Parsed calendar event date: {event_date} (UTC)")
            except (ValueError, AttributeError) as e:
                print(f"❌ Error parsing event date: {e}")
                return {"error": f"Could not parse calendar event date: {e}"}
        
        if not event_date:
            return {"error": "Calendar event has no valid start time"}
        
        # Extract Zoom meeting ID
        if not self.calendar:
            return {"error": "Calendar client not available"}
        
        print(f"🔍 Extracting Zoom meeting ID from calendar event...")
        meeting_info = self.calendar.extract_meeting_info(calendar_event)
        zoom_meeting_id = meeting_info.get('zoom_meeting_id')
        
        if not zoom_meeting_id:
            print(f"⚠️ No Zoom meeting ID found in calendar event")
            print(f"   Checked: description, location, conferenceData")
            print(f"   📝 Will generate summary with calendar information only (no transcript)")
            
            # Extract attendees from calendar event
            event_attendees = calendar_event.get('attendees', [])
            attendees_list = []
            for att in event_attendees:
                name = att.get('displayName') or att.get('email', '')
                if name:
                    attendees_list.append(name)
            
            # Format date
            formatted_date = event_date.strftime("%B %d, %Y at %I:%M %p")
            
            # Return calendar info without transcript (no error - we'll still generate a summary)
            return {
                "meeting_id": None,  # No meeting in DB since no transcript
                "transcript": None,  # No transcript available
                "meeting_title": event_title,
                "meeting_date": formatted_date,
                "recording_date": None,  # No recording
                "attendees": attendees_list,
                "no_zoom_recording": True  # Flag to indicate no Zoom recording
            }
        
        print(f"✅ Found Zoom meeting ID: {zoom_meeting_id}")
        print(f"   Strategy: Look up transcript by meeting ID only (no date/time constraints)")
        
        # Fetch transcript from Zoom - SIMPLIFIED: Only use meeting ID, no date matching
        try:
            print(f"\n🔗 Connecting to Zoom API...")
            print(f"   Initializing ZoomClient...")
            zoom_client = ZoomClient()
            print(f"   ✅ ZoomClient initialized successfully")
            
            # PRIMARY METHOD: UUID-based approach (same as test_get_transcript_by_uuid.py)
            # This is the proven method that works, so we prioritize it
            print(f"\n📹 PRIMARY: Using UUID-based approach (same as test_get_transcript_by_uuid.py)")
            print(f"   Strategy: Get UUID from meeting ID, then get recordings by UUID")
            
            # Get UUID from meeting ID (try to get most recent instance)
            meeting_uuid = None
            try:
                print(f"   🔍 Getting UUID from meeting ID {zoom_meeting_id}...")
                print(f"   📅 Event date: {event_date if event_date else 'None (will get most recent)'}")
                
                # Try to get UUID - use event_date if available, otherwise None to get most recent
                uuid_result = await zoom_client.get_meeting_uuid_from_id(
                    meeting_id=zoom_meeting_id,
                    expected_date=event_date if event_date else None
                )
                
                if uuid_result:
                    meeting_uuid = uuid_result
                    print(f"   ✅ Found UUID: {meeting_uuid}")
                    print(f"   ✅ UUID length: {len(meeting_uuid)} characters")
                else:
                    print(f"   ⚠️ Could not get UUID from meeting ID {zoom_meeting_id}")
                    print(f"   ⚠️ This might mean:")
                    print(f"      - Meeting has no past instances")
                    print(f"      - Meeting ID is incorrect")
                    print(f"      - Date doesn't match any instance (if date was provided)")
            except Exception as e:
                print(f"   ❌ ERROR getting UUID: {e}")
                import traceback
                print(f"   Traceback:")
                print(traceback.format_exc())
            
            # If we have UUID, use the proven UUID-based method (exact same as test file)
            # If the first UUID doesn't work, try other UUIDs as fallback
            if meeting_uuid:
                print(f"   📹 Getting transcript by UUID: {meeting_uuid[:30]}...")
                transcript = await zoom_client.get_transcript_by_uuid(meeting_uuid)
                
                if transcript:
                    print(f"✅ Successfully retrieved transcript using UUID-based method (same as test_get_transcript_by_uuid.py)")
                    recording_start_time_str = None  # Not available from UUID method
                    recording_uuid = meeting_uuid
                    recording_meeting_id = zoom_meeting_id
                else:
                    print(f"   ⚠️ First UUID did not return transcript")
                    print(f"   🔄 Trying other UUIDs as fallback...")
                    
                    # Get all UUIDs and try them in order
                    all_uuids = await zoom_client.get_all_meeting_uuids(
                        meeting_id=zoom_meeting_id,
                        expected_date=event_date if event_date else None
                    )
                    
                    print(f"   📋 Found {len(all_uuids)} UUID(s) to try")
                    
                    # Try each UUID until one works
                    for idx, (uuid, uuid_dt, time_diff) in enumerate(all_uuids, 1):
                        # Skip the first one (already tried)
                        if uuid == meeting_uuid:
                            continue
                        
                        print(f"   🔄 Trying UUID {idx}/{len(all_uuids)}: {uuid[:30]}... (Date: {uuid_dt.strftime('%Y-%m-%d %H:%M')})")
                        transcript = await zoom_client.get_transcript_by_uuid(uuid)
                        
                        if transcript:
                            print(f"✅ Successfully retrieved transcript using fallback UUID {idx}")
                            recording_start_time_str = None
                            recording_uuid = uuid
                            recording_meeting_id = zoom_meeting_id
                            break
                        else:
                            print(f"   ⚠️ UUID {idx} also did not have a recording")
                    
                    if not transcript:
                        print(f"   ❌ None of the {len(all_uuids)} UUID(s) had a recording available")
            
            # FALLBACK METHOD 1: Try direct transcript endpoint (by ID only)
            if not transcript:
                print(f"\n⚠️ UUID-based approach failed. Trying fallback: direct transcript endpoint...")
                print(f"   Strategy: Direct endpoint /meetings/{zoom_meeting_id}/transcript")
                transcript = await zoom_client.get_meeting_transcript_direct(zoom_meeting_id)
                
                if transcript:
                    print(f"✅ Successfully retrieved transcript using direct endpoint")
                    recording_start_time_str = None  # Not available from direct endpoint
                    recording_uuid = None
                    recording_meeting_id = zoom_meeting_id
                else:
                    print(f"   ⚠️ Direct transcript endpoint failed")
            
            # FALLBACK METHOD 2: Try recordings-based approach (by ID only, no date matching)
            if not transcript:
                print(f"\n⚠️ Direct endpoint failed. Trying fallback: recordings-based approach (by ID only)...")
                print(f"   Strategy: Get all recordings for meeting ID, find transcript (no date matching)")
                transcript = await zoom_client.get_meeting_transcript_from_recordings(
                    meeting_id=zoom_meeting_id,
                    expected_date=None  # No date constraint - just get transcript by meeting ID
                )
                
                if transcript:
                    print(f"✅ Found transcript using recordings-based method (by meeting ID only)")
                    recording_start_time_str = None  # Unknown from fallback
                    recording_uuid = None
                    recording_meeting_id = zoom_meeting_id
                else:
                    return {
                        "error": (
                            f"Found meeting '{event_title}' with Zoom ID {zoom_meeting_id}, "
                            "but no transcript was found. Tried:\n"
                            "1. UUID-based approach (get UUID → get recordings by UUID) - same as test_get_transcript_by_uuid.py\n"
                            "2. Direct transcript endpoint (/meetings/{id}/transcript)\n"
                            "3. Recordings-based search (all recordings for this meeting ID)\n\n"
                            "Please verify:\n"
                            "- The meeting was recorded on Zoom\n"
                            "- The transcript is available and processed\n"
                            "- The meeting ID is correct"
                        )
                    }
            
            # Create meeting in database
            print(f"\n💾 Creating meeting record in database...")
            print(f"   🔍 DEBUG: Before creating meeting record")
            print(f"   📋 meeting_title: {event_title}")
            print(f"   📋 calendar_event_id: {event_id}")
            print(f"   📋 transcript length: {len(transcript) if transcript else 0}")
            print(f"   📋 user_id: {user_id}")
            print(f"   📋 client_id: {client_id}")
            print(f"   🔗 db session: {self.db}")
            print(f"   🔗 db session active: {self.db.is_active if self.db else 'N/A'}")
            try:
                if 'T' in start_time_str:
                    scheduled_time = datetime.fromisoformat(start_time_str.replace('Z', '+00:00'))
                else:
                    scheduled_time = datetime.fromisoformat(start_time_str)
                if scheduled_time.tzinfo:
                    scheduled_time = scheduled_time.replace(tzinfo=None)
            except (ValueError, AttributeError):
                scheduled_time = datetime.utcnow()
            
            formatted_date = event_date.strftime("%B %d, %Y at %I:%M %p")
            recording_date_formatted = None
            if recording_start_time_str:
                try:
                    recording_dt = datetime.fromisoformat(recording_start_time_str.replace('Z', '+00:00'))
                    if recording_dt.tzinfo is None:
                        recording_dt = recording_dt.replace(tzinfo=timezone.utc)
                    else:
                        recording_dt = recording_dt.astimezone(timezone.utc)
                    recording_date_formatted = recording_dt.strftime("%B %d, %Y at %I:%M %p")
                except (ValueError, AttributeError):
                    recording_date_formatted = recording_start_time_str
            
            event_attendees = calendar_event.get('attendees', [])
            attendees_list = []
            for att in event_attendees:
                name = att.get('displayName') or att.get('email', '')
                if name:
                    attendees_list.append(name)
            
            # Store both meeting ID and UUID for future reference
            # Store UUID in zoom_meeting_id field (it can handle both formats)
            # For now, we'll store the numeric ID and use UUID for API calls
            meeting_data = MeetingCreate(
                user_id=user_id or 1,
                client_id=client_id,
                calendar_event_id=calendar_event.get('id'),
                zoom_meeting_id=zoom_meeting_id,  # Store numeric ID
                title=event_title,
                scheduled_time=scheduled_time,
                transcript=transcript,
                status="completed"
            )
            
            # Log the UUID for debugging (we'll use it for future API calls)
            if recording_uuid:
                print(f"   📝 Meeting UUID for future reference: {recording_uuid[:30]}...")
            
            db_meeting = self.memory.create_meeting(meeting_data)
            print(f"✅ Created meeting record (ID: {db_meeting.id})")
            print(f"   🔍 DEBUG: After creating meeting record")
            print(f"   📋 Meeting ID: {db_meeting.id}")
            print(f"   📋 Meeting title: {db_meeting.title}")
            if hasattr(db_meeting, 'calendar_event_id'):
                print(f"   📋 Calendar event ID: {db_meeting.calendar_event_id}")
            else:
                print(f"   📋 Calendar event ID: {calendar_event.get('id', 'N/A')}")
            print(f"   📋 Transcript length: {len(db_meeting.transcript) if db_meeting.transcript else 0}")
            print(f"   🔗 db session: {self.db}")
            print(f"   🔗 db session active: {self.db.is_active if self.db else 'N/A'}")
            
            # Verify the meeting can be retrieved immediately
            print(f"\n🔍 DEBUG: Verifying meeting can be retrieved immediately...")
            try:
                verify_meeting = self.memory.get_meeting_by_id(db_meeting.id)
                if verify_meeting:
                    print(f"   ✅ Meeting {db_meeting.id} verified via memory.get_meeting_by_id()")
                    print(f"      Title: {verify_meeting.title}, Transcript: {len(verify_meeting.transcript) if verify_meeting.transcript else 0} chars")
                else:
                    print(f"   ❌ Meeting {db_meeting.id} NOT found via memory.get_meeting_by_id()")
                    # Try direct query
                    if self.db:
                        from app.memory.models import Meeting
                        direct_verify = self.db.query(Meeting).filter(Meeting.id == db_meeting.id).first()
                        if direct_verify:
                            print(f"   ✅ Meeting {db_meeting.id} found via direct query")
                            print(f"      Title: {direct_verify.title}, Transcript: {len(direct_verify.transcript) if direct_verify.transcript else 0} chars")
                        else:
                            print(f"   ❌ Meeting {db_meeting.id} NOT found via direct query either")
                            print(f"   ⚠️ Possible session/transaction issue - meeting may not be committed yet")
                            # List all meetings for debugging
                            all_meetings = self.db.query(Meeting).all()
                            print(f"   📋 Total meetings in database: {len(all_meetings)}")
                            for m in all_meetings[:5]:  # Show first 5
                                print(f"      - Meeting ID={m.id}, Title='{m.title}', Created={m.created_at}")
            except Exception as e:
                print(f"   ❌ ERROR verifying meeting: {str(e)}")
                import traceback
                print(f"   📋 Traceback: {traceback.format_exc()}")
            
            return {
                "meeting_id": db_meeting.id,
                "transcript": transcript,
                "meeting_title": event_title,
                "meeting_date": formatted_date,
                "recording_date": recording_date_formatted,
                "attendees": attendees_list
            }
        
        except Exception as e:
            import traceback
            print(f"❌ Error processing calendar event: {e}\n{traceback.format_exc()}")
            return {"error": f"Error fetching transcript: {str(e)}"}
    
    async def _download_transcript(self, recording_files: list, zoom_client: ZoomClient) -> Optional[str]:
        """Download transcript from recording files."""
        print(f"   Scanning {len(recording_files)} recording file(s) for transcript...")
        
        async with httpx.AsyncClient() as client:
            for i, recording in enumerate(recording_files, 1):
                file_type = recording.get("file_type", "").upper()
                file_extension = recording.get("file_extension", "").lower()
                recording_type = recording.get("recording_type", "").upper()
                file_name = recording.get("file_name", "").lower()
                
                print(f"   File {i}: type={file_type}, extension={file_extension}, recording_type={recording_type}, name={file_name}")
                
                is_transcript = (
                    recording_type == "AUDIO_TRANSCRIPT" or
                    (file_type == "TRANSCRIPT" and recording_type != "TIMELINE") or
                    file_extension == "vtt" or
                    ("transcript" in file_name and "timeline" not in file_name)
                )
                
                if is_transcript:
                    print(f"   ✅ Found transcript file: {file_name}")
                    download_url = recording.get("download_url")
                    if download_url:
                        try:
                            print(f"   📥 Downloading from: {download_url[:80]}...")
                            headers = {
                                "Authorization": f"Bearer {zoom_client.access_token}",
                                "User-Agent": "MeetingAssistant/1.0"
                            }
                            
                            response = await client.get(download_url, headers=headers, timeout=30.0, follow_redirects=True)
                            response.raise_for_status()
                            
                            transcript_text = response.text
                            print(f"   📄 Downloaded {len(transcript_text)} characters")
                            
                            if file_extension == "vtt" or file_name.endswith(".vtt"):
                                print(f"   🔧 Parsing VTT format...")
                                transcript_text = zoom_client._parse_vtt(transcript_text)
                                print(f"   ✅ Parsed to {len(transcript_text)} characters of text")
                            
                            return transcript_text
                        except Exception as e:
                            print(f"   ❌ Error downloading transcript: {str(e)}")
                            continue
                    else:
                        print(f"   ⚠️ No download URL found for transcript file")
                else:
                    print(f"   ⏭️  Skipping (not a transcript file)")
        
        print(f"   ❌ No transcript file found in {len(recording_files)} recording file(s)")
        return None

