"""Tool execution module - dispatches to appropriate tool handlers."""

import re
from typing import Dict, Any, Optional
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from app.memory.repo import MemoryRepository
from app.tools.summarization import SummarizationTool
from app.tools.meeting_brief import MeetingBriefTool
from app.tools.followup import FollowUpTool
from app.integrations.google_calendar_client import GoogleCalendarClient
from app.orchestrator.meeting_finder import MeetingFinder


class ToolExecutor:
    """Handles tool execution based on intent."""
    
    def __init__(
        self,
        db: Session,
        memory: MemoryRepository,
        summarization_tool: SummarizationTool,
        meeting_brief_tool: MeetingBriefTool,
        followup_tool: FollowUpTool,
        get_calendar_func
    ):
        self.db = db
        self.memory = memory
        self.summarization_tool = summarization_tool
        self.meeting_brief_tool = meeting_brief_tool
        self.followup_tool = followup_tool
        self._get_calendar = get_calendar_func
    
    async def execute(
        self,
        intent: str,
        message: str,
        context: Dict[str, Any],
        user_id: Optional[int],
        client_id: Optional[int],
        extracted_info: Dict[str, Any],
        selected_meeting_id: Optional[int] = None,
        selected_calendar_event_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Execute the appropriate tool based on intent."""
        try:
            if intent == "meeting_brief":
                return await self._execute_meeting_brief(message, extracted_info, client_id, user_id)
            
            elif intent == "summarization":
                return await self._execute_summarization(
                    message, extracted_info, user_id, client_id,
                    selected_meeting_id, selected_calendar_event_id
                )
            
            elif intent == "followup":
                return await self._execute_followup(extracted_info, client_id, user_id)
            
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
        message: str,
        extracted_info: Dict[str, Any],
        client_id: Optional[int],
        user_id: Optional[int]
    ) -> Dict[str, Any]:
        """Execute meeting brief tool."""
        # Check if there's meeting context
        has_meeting_context = (
            extracted_info.get("calendar_event_id") or
            extracted_info.get("meeting_id") or
            extracted_info.get("meeting_date") or
            extracted_info.get("client_name") or
            any(keyword in message.lower() for keyword in [
                "meeting", "brief", "prepare", "upcoming", "tomorrow",
                "today", "next week", "calendar", "schedule"
            ])
        )
        
        if not has_meeting_context:
            return None
        
        # Extract client name
        import re
        client_name = extracted_info.get("client_name")
        if not client_name:
            patterns = [
                r'meeting with\s+([A-Z][A-Za-z\s]+?)(?:\s|$|,|\.)',
                r'prepare.*?for.*?meeting.*?with\s+([A-Z][A-Za-z\s]+?)(?:\s|$|,|\.)',
                r'brief.*?for.*?([A-Z][A-Za-z\s]+?)(?:\s|$|,|\.)',
            ]
            for pattern in patterns:
                match = re.search(pattern, message, re.IGNORECASE)
                if match:
                    client_name = match.group(1).strip()
                    client_name = re.sub(r'\b(for|with|the|a|an)\b', '', client_name, flags=re.IGNORECASE).strip()
                    if client_name:
                        break
        
        result = await self.meeting_brief_tool.generate_brief(
            meeting_id=extracted_info.get("meeting_id"),
            calendar_event_id=extracted_info.get("calendar_event_id"),
            client_id=client_id,
            user_id=user_id,
            client_name=client_name
        )
        
        return {
            "tool_name": "meeting_brief",
            "result": result
        }
    
    async def _execute_summarization(
        self,
        message: str,
        extracted_info: Dict[str, Any],
        user_id: Optional[int],
        client_id: Optional[int],
        selected_meeting_id: Optional[int],
        selected_calendar_event_id: Optional[str]
    ) -> Dict[str, Any]:
        """Execute summarization tool."""
        import re
        from app.memory.models import Meeting
        
        print(f"\n{'='*80}")
        print(f"🔍 SUMMARIZATION REQUEST - Starting processing")
        print(f"{'='*80}")
        print(f"📝 Input message: '{message}'")
        print(f"   user_id: {user_id}")
        print(f"   client_id: {client_id}")
        print(f"   selected_meeting_id: {selected_meeting_id}")
        print(f"   selected_calendar_event_id: {selected_calendar_event_id}")
        print(f"   extracted_info: {extracted_info}")
        
        # Parse meeting selection from message
        meeting_id = None
        selected_meeting_number = None
        calendar_event_id_from_selection = None
        client_name = extracted_info.get("client_name")
        
        print(f"\n🔎 Step 1: Parsing meeting selection from message...")
        
        # Handle UI selections
        if selected_meeting_id:
            print(f"   ✅ Found selected_meeting_id from UI: {selected_meeting_id}")
            db_meeting = self.db.query(Meeting).filter(Meeting.id == selected_meeting_id).first()
            if db_meeting:
                meeting_id = selected_meeting_id
                print(f"   ✅ Meeting found in database: {db_meeting.title}")
            else:
                meeting_id = None  # Will search calendar
                print(f"   ⚠️ Meeting {selected_meeting_id} not found in database, will search calendar")
        elif selected_calendar_event_id:
            print(f"   ✅ Found selected_calendar_event_id from UI: {selected_calendar_event_id}")
            calendar_event_id_from_selection = selected_calendar_event_id
            db_meeting = self.db.query(Meeting).filter(
                Meeting.calendar_event_id == calendar_event_id_from_selection
            ).first()
            if db_meeting:
                meeting_id = db_meeting.id
                print(f"   ✅ Found meeting in database for calendar event: {db_meeting.id}")
            else:
                print(f"   ⚠️ No database meeting found for calendar event, will search calendar")
        else:
            # Parse from message
            print(f"   🔍 Parsing message for meeting identifiers...")
            
            # First, check if there's a date in the message - if so, don't treat numbers as meeting numbers
            # Date patterns: "november 21st", "nov 21", "21st", "21", "2024-11-21", "11/21/2024"
            date_patterns = [
                r'\b(january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{1,2}(?:st|nd|rd|th)?\b',
                r'\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\s+\d{1,2}(?:st|nd|rd|th)?\b',
                r'\b\d{1,2}(?:st|nd|rd|th)\s+(?:of\s+)?(january|february|march|april|may|june|july|august|september|october|november|december)\b',
                r'\b\d{4}-\d{2}-\d{2}\b',  # ISO format
                r'\b\d{1,2}/\d{1,2}/\d{4}\b',  # MM/DD/YYYY
                r'\b\d{1,2}-\d{1,2}-\d{4}\b',  # MM-DD-YYYY
            ]
            
            has_date_in_message = any(re.search(pattern, message, re.IGNORECASE) for pattern in date_patterns)
            
            if has_date_in_message:
                print(f"   📅 Date detected in message - will be more careful about parsing meeting numbers")
            
            # Only match meeting numbers if they're clearly meeting numbers (not part of dates)
            # Pattern: "meeting 3", "number 2", "summarize meeting 1", etc.
            # But NOT: "november 21st" (21 is part of date)
            # More specific pattern: must have "meeting" or "number" before the digit, and NOT have date suffixes after
            meeting_number_match = None
            if has_date_in_message:
                # If date is present, be very strict - only match explicit "meeting X" or "number X"
                # and ensure the number is NOT followed by date suffixes
                meeting_number_match = re.search(
                    r'\b(?:meeting|number)\s+(\d+)(?!\s*(?:st|nd|rd|th|of|january|february|march|april|may|june|july|august|september|october|november|december))',
                    message,
                    re.IGNORECASE
                )
                if meeting_number_match:
                    print(f"   ✅ Found explicit meeting number pattern (date context): {meeting_number_match.group(1)}")
                else:
                    print(f"   ℹ️ No explicit meeting number found (date detected, being strict)")
            else:
                # No date, can be more lenient
                meeting_number_match = re.search(r'(?:summarize\s+)?(?:meeting\s+)?(?:number\s+)?(\d+)', message, re.IGNORECASE)
                if meeting_number_match:
                    # Double-check it's not part of a date by checking context
                    match_pos = meeting_number_match.start()
                    match_end = meeting_number_match.end()
                    # Check if there's a month name or date suffix near the number
                    context_before = message[max(0, match_pos-20):match_pos].lower()
                    context_after = message[match_end:min(len(message), match_end+20)].lower()
                    months = ['january', 'february', 'march', 'april', 'may', 'june', 'july', 'august', 'september', 'october', 'november', 'december',
                             'jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec']
                    date_suffixes = ['st', 'nd', 'rd', 'th']
                    
                    if any(month in context_before for month in months) or any(suffix in context_after for suffix in date_suffixes):
                        print(f"   ⚠️ Number {meeting_number_match.group(1)} appears to be part of a date, ignoring")
                        meeting_number_match = None
                    else:
                        print(f"   ✅ Found meeting number (no date context): {meeting_number_match.group(1)}")
            
            meeting_id_match = re.search(r'meeting\s+id\s+(\d+)', message, re.IGNORECASE)
            calendar_event_match = re.search(r'calendar\s+event\s+([a-zA-Z0-9_\-]+)', message, re.IGNORECASE)
            
            if meeting_id_match:
                parsed_meeting_id = int(meeting_id_match.group(1))
                print(f"   ✅ Found meeting_id in message: {parsed_meeting_id}")
                db_meeting = self.db.query(Meeting).filter(Meeting.id == parsed_meeting_id).first()
                if db_meeting:
                    meeting_id = parsed_meeting_id
                    print(f"   ✅ Meeting found in database: {db_meeting.title}")
                else:
                    print(f"   ⚠️ Meeting {parsed_meeting_id} not found in database")
            elif meeting_number_match:
                selected_meeting_number = int(meeting_number_match.group(1))
                print(f"   ✅ Found meeting number in message: {selected_meeting_number}")
            elif calendar_event_match:
                calendar_event_id_from_selection = calendar_event_match.group(1)
                print(f"   ✅ Found calendar_event_id in message: {calendar_event_id_from_selection}")
                db_meeting = self.db.query(Meeting).filter(
                    Meeting.calendar_event_id == calendar_event_id_from_selection
                ).first()
                if db_meeting:
                    meeting_id = db_meeting.id
                    print(f"   ✅ Meeting found in database: {db_meeting.id}")
                else:
                    print(f"   ⚠️ No database meeting found for calendar event")
            else:
                print(f"   ℹ️ No meeting identifier found in message")
        
        print(f"   📊 After parsing: meeting_id={meeting_id}, selected_meeting_number={selected_meeting_number}, calendar_event_id={calendar_event_id_from_selection}")
        
        # Extract date from extracted_info first, then from message directly
        print(f"\n📅 Step 2a: Extracting date from message...")
        extracted_date = None
        try:
            extracted_date = extracted_info.get("date")
            print(f"   Date from extracted_info: {extracted_date}")
        except Exception as e:
            print(f"   ⚠️ Error extracting date from extracted_info: {str(e)}")
        
        # Also try to extract date directly from message if not found in extracted_info
        if not extracted_date:
            print(f"   🔍 No date in extracted_info, searching message directly...")
            # Enhanced date patterns to catch more formats
            date_patterns = [
                r'\b(january|february|march|april|may|june|july|august|september|october|november|december)\s+(\d{1,2})(?:st|nd|rd|th)?\b',
                r'\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\s+(\d{1,2})(?:st|nd|rd|th)?\b',
                r'\b(\d{1,2})(?:st|nd|rd|th)?\s+(?:of\s+)?(january|february|march|april|may|june|july|august|september|october|november|december)\b',
                r'\b(\d{1,2})(?:st|nd|rd|th)?\s+(?:of\s+)?(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\b',
                r'\b(?:the\s+)?(\d{1,2})(?:st|nd|rd|th)\b',  # "21st", "the 21st"
                r'\b(twenty[-\s]?first|twenty[-\s]?second|twenty[-\s]?third|twenty[-\s]?fourth|twenty[-\s]?fifth|twenty[-\s]?sixth|twenty[-\s]?seventh|twenty[-\s]?eighth|twenty[-\s]?ninth|thirtieth|thirty[-\s]?first)\s+(?:of\s+)?(january|february|march|april|may|june|july|august|september|october|november|december)\b',
                r'\b\d{4}-\d{2}-\d{2}\b',  # ISO format
                r'\b\d{1,2}/\d{1,2}(?:/\d{2,4})?\b',  # MM/DD/YYYY or MM/DD/YY or MM/DD
                r'\b\d{1,2}-\d{1,2}-\d{4}\b',  # MM-DD-YYYY
            ]
            
            for pattern in date_patterns:
                match = re.search(pattern, message, re.IGNORECASE)
                if match:
                    extracted_date = match.group(0)
                    print(f"   ✅ Found date pattern in message: '{extracted_date}'")
                    break
        
        # Parse date if provided
        target_date = None
        try:
            if extracted_date:
                target_date = self._parse_date(extracted_date)
                if target_date:
                    print(f"   ✅ Parsed date: {target_date}")
                else:
                    print(f"   ⚠️ Could not parse date: {extracted_date}")
                    # Try parsing the original message string directly
                    print(f"   🔄 Attempting to parse date from full message context...")
                    target_date = self._parse_date(message)
                    if target_date:
                        print(f"   ✅ Successfully parsed date from message: {target_date}")
        except Exception as e:
            print(f"   ❌ ERROR parsing date: {str(e)}")
            target_date = None
        
        # Extract client name if not provided
        print(f"\n🔎 Step 2b: Extracting client name from message...")
        print(f"   Initial client_name from extracted_info: {client_name}")
        
        try:
            if not client_name:
                # Improved patterns to catch various formats (case-insensitive):
                # - "my last MTCA meeting" or "my last mtca meeting"
                # - "MTCA meeting" or "mtca meeting"
                # - "meeting with MTCA" or "meeting with mtca"
                # - "last meeting with Good Health"
                patterns = [
                    r'my\s+last\s+([A-Za-z]{2,})\s+meeting',  # "my last MTCA meeting" or "my last mtca meeting"
                    r'last\s+([A-Za-z]{2,})\s+meeting',  # "last MTCA meeting" or "last mtca meeting"
                    r'summarize.*?meeting.*?with\s+([A-Za-z][A-Za-z0-9]+(?:\s+[A-Za-z][A-Za-z0-9]+){0,3})(?:\s|$|,|\.|on)',
                    r'last meeting.*?with\s+([A-Za-z][A-Za-z0-9]+(?:\s+[A-Za-z][A-Za-z0-9]+){0,3})(?:\s|$|,|\.|on)',
                    r'meeting.*?with\s+([A-Za-z][A-Za-z0-9]+(?:\s+[A-Za-z][A-Za-z0-9]+){0,3})(?:\s|$|,|\.|on)',  # "meeting with mtca" or "meeting with MTCA"
                    r'with\s+([A-Za-z]{2,})(?:\s|$|,|\.|on)',  # "with MTCA" or "with mtca"
                    r'([A-Za-z]{2,})\s+meeting',  # "MTCA meeting" or "mtca meeting" (any case)
                    r'([A-Za-z][A-Za-z]+(?:\s+[A-Za-z][A-Za-z]+){0,2})\s+meeting',  # "Good Health meeting"
                ]
                for i, pattern in enumerate(patterns, 1):
                    match = re.search(pattern, message, re.IGNORECASE)
                    if match:
                        extracted = match.group(1).strip()
                        print(f"   Pattern {i} matched: '{extracted}'")
                        client_name = extracted
                        
                        # Normalize: if it's a short acronym-like string (2-6 chars, all letters), convert to uppercase
                        if len(client_name) >= 2 and len(client_name) <= 6 and client_name.isalpha():
                            client_name = client_name.upper()
                            print(f"   Normalized to uppercase acronym: '{client_name}'")
                        else:
                            # For longer names, remove common words and capitalize properly
                            client_name = re.sub(r'\b(for|with|the|a|an|my|last|summarize|meeting|on)\b', '', client_name, flags=re.IGNORECASE).strip()
                            # Capitalize first letter of each word
                            client_name = ' '.join(word.capitalize() for word in client_name.split())
                            print(f"   After removing common words and capitalizing: '{client_name}'")
                        
                        common_words = {'summarize', 'meeting', 'last', 'my', 'the', 'a', 'an', 'for', 'with', 'on'}
                        if client_name and len(client_name) >= 2 and client_name.lower() not in common_words:
                            print(f"   ✅ Valid client name extracted: '{client_name}'")
                            break
                        else:
                            print(f"   ⚠️ Extracted name '{client_name}' is a common word, ignoring")
                            client_name = None
        except Exception as e:
            print(f"   ❌ ERROR extracting client name: {str(e)}")
            import traceback
            print(f"   📋 Traceback: {traceback.format_exc()}")
            client_name = None
        
        # Validate client name
        try:
            common_words = {'summarize', 'meeting', 'last', 'my', 'the', 'a', 'an', 'for', 'with', 'prepare', 'brief'}
            if client_name and client_name.lower() in common_words:
                print(f"   ⚠️ Client name '{client_name}' is in common words list, clearing it")
                client_name = None
        except Exception as e:
            print(f"   ⚠️ ERROR validating client name: {str(e)}")
        
        print(f"   📊 Final client_name: {client_name}")
        
        # IMPORTANT: If we have a selected_meeting_number, we should NOT use client_name
        # because the user is selecting from a previously shown list
        # BUT: Only clear client_name if we also have a date, because the number might be from a date
        if selected_meeting_number:
            # Check if the number is likely from a date (e.g., "21st" in "november 21st")
            # If we have a date extracted, the number is probably from the date, not a meeting selection
            if target_date:
                print(f"\n⚠️ WARNING: Found number {selected_meeting_number} but also have date {target_date}")
                print(f"   This number is likely from the date (e.g., '21st'), NOT a meeting selection")
                print(f"   Ignoring meeting number and keeping client_name and date for search")
                selected_meeting_number = None  # Clear it - it's from the date
            else:
                print(f"\n⚠️ IMPORTANT: User selected meeting number {selected_meeting_number} from list")
                print(f"   Clearing client_name to avoid searching by client name instead of using the number")
                client_name = None
        
        # Find meeting in database first
        print(f"\n🔎 Step 3: Searching for meeting...")
        try:
            calendar = self._get_calendar()
        except Exception as e:
            print(f"   ❌ ERROR getting calendar client: {str(e)}")
            import traceback
            print(f"   📋 Traceback: {traceback.format_exc()}")
            calendar = None
        
        try:
            meeting_finder = MeetingFinder(self.db, self.memory, calendar)
        except Exception as e:
            print(f"   ❌ ERROR creating MeetingFinder: {str(e)}")
            import traceback
            print(f"   📋 Traceback: {traceback.format_exc()}")
            return {
                "tool_name": "summarization",
                "error": f"Failed to initialize meeting finder: {str(e)}"
            }
        
        try:
            if not meeting_id:
                print(f"   🔍 No meeting_id yet, searching database...")
                print(f"      Parameters: client_id={client_id}, user_id={user_id}, client_name={client_name}")
                meeting_id = meeting_finder.find_meeting_in_database(
                    meeting_id=meeting_id,
                    client_id=client_id,
                    user_id=user_id,
                    client_name=client_name
                )
                print(f"   📊 Database search result: meeting_id={meeting_id}")
            else:
                print(f"   ✅ Already have meeting_id={meeting_id}, skipping database search")
        except Exception as e:
            print(f"   ❌ ERROR searching database: {str(e)}")
            import traceback
            print(f"   📋 Traceback: {traceback.format_exc()}")
            meeting_id = None  # Continue to calendar search
        
        # Verify meeting exists if we have an ID
        try:
            if meeting_id:
                from app.memory.models import Meeting
                db_meeting = self.db.query(Meeting).filter(Meeting.id == meeting_id).first()
                if not db_meeting:
                    print(f"   ⚠️ Meeting {meeting_id} not found in database, clearing it")
                    meeting_id = None  # Clear it to search calendar
                else:
                    print(f"   ✅ Verified meeting {meeting_id} exists: {db_meeting.title}")
        except Exception as e:
            print(f"   ❌ ERROR verifying meeting: {str(e)}")
            import traceback
            print(f"   📋 Traceback: {traceback.format_exc()}")
            meeting_id = None  # Clear it to search calendar
        
        # If no meeting in database, search calendar
        calendar_event = None
        
        if not meeting_id and calendar:
            try:
                print(f"\n🔎 Step 4: Searching Google Calendar...")
                print(f"   Parameters: client_name={client_name}, target_date={target_date}, selected_meeting_number={selected_meeting_number}, calendar_event_id={calendar_event_id_from_selection or selected_calendar_event_id}")
                calendar_event, meeting_options = meeting_finder.find_meeting_in_calendar(
                    client_name=client_name,
                    target_date=target_date,  # Pass the parsed date
                    selected_meeting_number=selected_meeting_number,
                    calendar_event_id=calendar_event_id_from_selection or selected_calendar_event_id,
                    user_id=user_id
                )
                print(f"   📊 Calendar search result: calendar_event={'found' if calendar_event else 'None'}, meeting_options={'found' if meeting_options else 'None'}")
                
                # If meeting options are returned, user needs to select before we fetch transcript
                if meeting_options:
                    print(f"   ✅ Returning {len(meeting_options)} meeting option(s) for user selection")
                    return {
                        "tool_name": "summarization",
                        "result": None,
                        "meeting_options": meeting_options,
                        "requires_selection": True
                    }
            except Exception as e:
                import traceback
                print(f"   ❌ ERROR searching calendar: {str(e)}")
                print(f"   📋 Traceback: {traceback.format_exc()}")
                calendar_event = None
        elif not calendar:
            print(f"   ⚠️ Calendar client not available, skipping calendar search")
        
        # Handle errors
        print(f"\n🔎 Step 5: Final check before execution...")
        print(f"   meeting_id: {meeting_id}")
        print(f"   calendar_event: {'found' if calendar_event else 'None'}")
        
        if not meeting_id and not calendar_event:
            print(f"   ❌ ERROR: No meeting found!")
            calendar_error = getattr(self, '_calendar_error', None)
            if calendar_error or not calendar:
                print(f"   Reason: Calendar error - {calendar_error if calendar_error else 'Calendar not initialized'}")
                return {
                    "tool_name": "summarization",
                    "error": (
                        "I need to connect to your Google Calendar to find meetings. "
                        "Please make sure you have:\n"
                        "- Authenticated with Google (check if token.json exists)\n"
                        "- Set up your Google OAuth credentials in .env\n"
                        "- Run the app in an environment where browser authentication is possible\n\n"
                        f"Error: {calendar_error if calendar_error else 'Calendar client not initialized'}"
                    )
                }
            else:
                error_msg = "No meeting found to summarize."
                common_words_check = {'summarize', 'meeting', 'last', 'my', 'the', 'a', 'an', 'for', 'with', 'prepare', 'brief'}
                if client_name and client_name.lower() not in common_words_check:
                    error_msg += f" I couldn't find any meetings for '{client_name}' in your database or calendar."
                    print(f"   Reason: Searched for client_name='{client_name}' but found nothing")
                else:
                    error_msg += " I couldn't find any meetings in your database or calendar."
                    print(f"   Reason: No meeting_id or calendar_event found, and no valid client_name to search")
                error_msg += " Please specify which meeting you'd like to summarize, or make sure your meetings are properly recorded and linked."
                
                return {
                    "tool_name": "summarization",
                    "error": error_msg
                }
        
        # Execute summarization
        print(f"\n✅ Step 6: Executing summarization...")
        print(f"   Using meeting_id={meeting_id} or calendar_event={'found' if calendar_event else 'None'}")
        
        try:
            # Update calendar reference in tool if needed
            if calendar and not self.summarization_tool.calendar:
                self.summarization_tool.calendar = calendar
            
            result = await self.summarization_tool.summarize_meeting(
                meeting_id=meeting_id,
                calendar_event=calendar_event,
                client_name=client_name,
                user_id=user_id,
                client_id=client_id
            )
            
            # Check if result has error
            if result.get("error"):
                print(f"   ❌ Summarization error: {result.get('error')}")
                return {
                    "tool_name": "summarization",
                    "error": result["error"]
                }
            
            print(f"   ✅ Summarization successful!")
            print(f"{'='*80}\n")
        except Exception as e:
            import traceback
            error_msg = f"An unexpected error occurred while summarizing the meeting: {str(e)}"
            print(f"   ❌ EXCEPTION in summarization: {str(e)}")
            print(f"   📋 Traceback: {traceback.format_exc()}")
            return {
                "tool_name": "summarization",
                "error": error_msg
            }
        
        return {
            "tool_name": "summarization",
            "result": result
        }
    
    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """
        Parse date string into datetime object.
        Handles formats like:
        - "November 21st", "Nov 21", "November 21", "21st", "the 21st"
        - "2024-11-21", "11/21/2024", "11/21/25", "11/21"
        - Written numbers: "twenty-first", "twenty first"
        - Relative dates: "yesterday", "last week"
        """
        if not date_str:
            return None
        
        date_str = date_str.strip().lower()
        now = datetime.now(timezone.utc)
        current_year = now.year
        
        # Try parsing common date formats
        try:
            # ISO format: "2024-11-21"
            if re.match(r'^\d{4}-\d{2}-\d{2}', date_str):
                parsed = datetime.fromisoformat(date_str)
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=timezone.utc)
                return parsed
            
            # Slash format: "11/21/2024", "11/21/25", "11/21"
            if '/' in date_str:
                parts = date_str.split('/')
                if len(parts) == 3:
                    month, day, year = map(int, parts)
                    # Handle 2-digit year
                    if year < 100:
                        if year <= 50:  # Assume 2000s
                            year += 2000
                        else:  # Assume 1900s
                            year += 1900
                    return datetime(year, month, day, tzinfo=timezone.utc)
                elif len(parts) == 2:
                    month, day = map(int, parts)
                    # Use current year, or previous year if date has passed
                    year = current_year
                    try:
                        parsed = datetime(year, month, day, tzinfo=timezone.utc)
                        if parsed > now:
                            parsed = datetime(year - 1, month, day, tzinfo=timezone.utc)
                        return parsed
                    except ValueError:
                        pass
            
            # Month name formats: "November 21st", "November 21", "Nov 21", "21st of November"
            month_patterns = [
                (r'(january|february|march|april|may|june|july|august|september|october|november|december)\s+(\d{1,2})(?:st|nd|rd|th)?', '%B %d'),
                (r'(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\s+(\d{1,2})(?:st|nd|rd|th)?', '%b %d'),
                (r'(\d{1,2})(?:st|nd|rd|th)?\s+(?:of\s+)?(january|february|march|april|may|june|july|august|september|october|november|december)', '%d %B'),
                (r'(\d{1,2})(?:st|nd|rd|th)?\s+(?:of\s+)?(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)', '%d %b'),
            ]
            
            for pattern, date_format in month_patterns:
                match = re.search(pattern, date_str, re.IGNORECASE)
                if match:
                    if date_format.startswith('%d'):  # Day first format
                        day = match.group(1)
                        month_name = match.group(2)
                    else:  # Month first format
                        month_name = match.group(1)
                        day = match.group(2)
                    
                    # Capitalize month name for strptime
                    month_name = month_name.capitalize()
                    if len(month_name) == 3:
                        # Abbreviation
                        month_name = month_name.capitalize()
                    else:
                        # Full month name
                        month_name = month_name.capitalize()
                    
                    year = current_year
                    try:
                        # Try with current year
                        if date_format.startswith('%d'):
                            parsed = datetime.strptime(f"{day} {month_name} {year}", f"{date_format} %Y")
                        else:
                            parsed = datetime.strptime(f"{month_name} {day} {year}", f"{date_format} %Y")
                        
                        # If date is in the future, use previous year
                        if parsed > now:
                            year = current_year - 1
                            if date_format.startswith('%d'):
                                parsed = datetime.strptime(f"{day} {month_name} {year}", f"{date_format} %Y")
                            else:
                                parsed = datetime.strptime(f"{month_name} {day} {year}", f"{date_format} %Y")
                        
                        return parsed.replace(tzinfo=timezone.utc)
                    except ValueError:
                        continue
            
            # Just day with suffix: "21st", "the 21st" (assume current month/year or previous if passed)
            day_match = re.search(r'(?:the\s+)?(\d{1,2})(?:st|nd|rd|th)', date_str)
            if day_match:
                day = int(day_match.group(1))
                # Try current month first
                try:
                    parsed = datetime(current_year, now.month, day, tzinfo=timezone.utc)
                    if parsed > now:
                        # Try previous month
                        if now.month == 1:
                            parsed = datetime(current_year - 1, 12, day, tzinfo=timezone.utc)
                        else:
                            parsed = datetime(current_year, now.month - 1, day, tzinfo=timezone.utc)
                    return parsed
                except ValueError:
                    pass
            
            # Written numbers: "twenty-first", "twenty first" (convert to numeric)
            written_numbers = {
                'first': 1, 'second': 2, 'third': 3, 'fourth': 4, 'fifth': 5,
                'sixth': 6, 'seventh': 7, 'eighth': 8, 'ninth': 9, 'tenth': 10,
                'eleventh': 11, 'twelfth': 12, 'thirteenth': 13, 'fourteenth': 14, 'fifteenth': 15,
                'sixteenth': 16, 'seventeenth': 17, 'eighteenth': 18, 'nineteenth': 19, 'twentieth': 20,
                'twenty-first': 21, 'twenty first': 21, 'twentysecond': 22, 'twenty second': 22,
                'twenty-third': 23, 'twenty third': 23, 'twenty-fourth': 24, 'twenty fourth': 24,
                'twenty-fifth': 25, 'twenty fifth': 25, 'twenty-sixth': 26, 'twenty sixth': 26,
                'twenty-seventh': 27, 'twenty seventh': 27, 'twenty-eighth': 28, 'twenty eighth': 28,
                'twenty-ninth': 29, 'twenty ninth': 29, 'thirtieth': 30, 'thirty-first': 31, 'thirty first': 31
            }
            
            for written, numeric in written_numbers.items():
                if written in date_str:
                    # Look for month name in the string
                    month_pattern = r'(january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)'
                    month_match = re.search(month_pattern, date_str, re.IGNORECASE)
                    if month_match:
                        month_name = month_match.group(1).capitalize()
                        if len(month_name) == 3:
                            month_format = '%b'
                        else:
                            month_format = '%B'
                        
                        year = current_year
                        try:
                            parsed = datetime.strptime(f"{month_name} {numeric} {year}", f"{month_format} %d %Y")
                            if parsed > now:
                                parsed = datetime.strptime(f"{month_name} {numeric} {year - 1}", f"{month_format} %d %Y")
                            return parsed.replace(tzinfo=timezone.utc)
                        except ValueError:
                            pass
            
            # Relative dates
            if 'yesterday' in date_str:
                return (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
            elif 'today' in date_str:
                return now.replace(hour=0, minute=0, second=0, microsecond=0)
            elif 'tomorrow' in date_str:
                return (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
            
        except Exception as e:
            print(f"   ⚠️ Error parsing date '{date_str}': {str(e)}")
        
        return None
    
    async def _execute_followup(
        self,
        extracted_info: Dict[str, Any],
        client_id: Optional[int],
        user_id: Optional[int]
    ) -> Dict[str, Any]:
        """Execute follow-up tool."""
        meeting_id = extracted_info.get("meeting_id")
        if not meeting_id and client_id:
            meetings = self.memory.get_meetings_by_client(client_id, limit=5)
            completed_meetings = [m for m in meetings if m.status == "completed"]
            if completed_meetings:
                meeting_id = completed_meetings[0].id
        
        result = await self.followup_tool.generate_followup(
            meeting_id=meeting_id,
            client_id=client_id
        )
        
        return {
            "tool_name": "followup",
            "result": result
        }

