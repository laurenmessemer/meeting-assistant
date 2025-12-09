"""Data preparation module - handles parsing and extracting information from user input."""

import re
from typing import Dict, Any, Optional
from datetime import datetime, timezone, timedelta


class DataPreparator:
    """Handles parsing and extracting information from user messages."""
    
    def parse_date(self, date_str: str) -> Optional[datetime]:
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
    
    def extract_client_name(self, message: str, extracted_info: Dict[str, Any]) -> Optional[str]:
        """
        Extract client name from message and extracted_info.
        
        Args:
            message: User message
            extracted_info: Extracted info from intent recognition
        
        Returns:
            Client name or None
        """
        client_name = extracted_info.get("client_name")
        
        if not client_name:
            # Improved patterns to catch various formats (case-insensitive):
            patterns = [
                r'my\s+last\s+([A-Za-z]{2,})\s+meeting',
                r'last\s+([A-Za-z]{2,})\s+meeting',
                r'summarize.*?meeting.*?with\s+([A-Za-z][A-Za-z0-9]+(?:\s+[A-Za-z][A-Za-z0-9]+){0,3})(?:\s|$|,|\.|on)',
                r'last meeting.*?with\s+([A-Za-z][A-Za-z0-9]+(?:\s+[A-Za-z][A-Za-z0-9]+){0,3})(?:\s|$|,|\.|on)',
                r'meeting.*?with\s+([A-Za-z][A-Za-z0-9]+(?:\s+[A-Za-z][A-Za-z0-9]+){0,3})(?:\s|$|,|\.|on)',
                r'with\s+([A-Za-z]{2,})(?:\s|$|,|\.|on)',
                r'([A-Za-z]{2,})\s+meeting',
                r'([A-Za-z][A-Za-z]+(?:\s+[A-Za-z][A-Za-z]+){0,2})\s+meeting',
            ]
            for pattern in patterns:
                match = re.search(pattern, message, re.IGNORECASE)
                if match:
                    extracted = match.group(1).strip()
                    
                    # Normalize: if it's a short acronym-like string (2-6 chars, all letters), convert to uppercase
                    if len(extracted) >= 2 and len(extracted) <= 6 and extracted.isalpha():
                        client_name = extracted.upper()
                    else:
                        # For longer names, remove common words and capitalize properly
                        client_name = re.sub(r'\b(for|with|the|a|an|my|last|summarize|meeting|on)\b', '', extracted, flags=re.IGNORECASE).strip()
                        # Capitalize first letter of each word
                        client_name = ' '.join(word.capitalize() for word in client_name.split())
                    
                    common_words = {'summarize', 'meeting', 'last', 'my', 'the', 'a', 'an', 'for', 'with', 'on'}
                    if client_name and len(client_name) >= 2 and client_name.lower() not in common_words:
                        return client_name
        
        # Validate client name
        common_words = {'summarize', 'meeting', 'last', 'my', 'the', 'a', 'an', 'for', 'with', 'prepare', 'brief'}
        if client_name and client_name.lower() in common_words:
            return None
        
        return client_name
    
    def extract_meeting_selection(
        self,
        message: str,
        extracted_info: Dict[str, Any],
        selected_meeting_id: Optional[int],
        selected_calendar_event_id: Optional[str]
    ) -> Dict[str, Any]:
        """
        Extract meeting selection information from message and UI selections.
        
        Returns:
            Dict with meeting_id, selected_meeting_number, calendar_event_id, target_date, client_name
        """
        result = {
            "meeting_id": None,
            "selected_meeting_number": None,
            "calendar_event_id": None,
            "target_date": None,
            "client_name": None
        }
        
        # Handle UI selections
        if selected_meeting_id:
            result["meeting_id"] = selected_meeting_id
            return result
        
        if selected_calendar_event_id:
            result["calendar_event_id"] = selected_calendar_event_id
            return result
        
        # Parse from message
        # Extract date
        extracted_date = extracted_info.get("date")
        if not extracted_date:
            # Try to extract date directly from message
            date_patterns = [
                r'\b(january|february|march|april|may|june|july|august|september|october|november|december)\s+(\d{1,2})(?:st|nd|rd|th)?\b',
                r'\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\s+(\d{1,2})(?:st|nd|rd|th)?\b',
                r'\b(\d{1,2})(?:st|nd|rd|th)?\s+(?:of\s+)?(january|february|march|april|may|june|july|august|september|october|november|december)\b',
                r'\b(\d{1,2})(?:st|nd|rd|th)?\s+(?:of\s+)?(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\b',
                r'\b(?:the\s+)?(\d{1,2})(?:st|nd|rd|th)\b',
                r'\b\d{4}-\d{2}-\d{2}\b',
                r'\b\d{1,2}/\d{1,2}(?:/\d{2,4})?\b',
                r'\b\d{1,2}-\d{1,2}-\d{4}\b',
            ]
            
            for pattern in date_patterns:
                match = re.search(pattern, message, re.IGNORECASE)
                if match:
                    extracted_date = match.group(0)
                    break
        
        if extracted_date:
            result["target_date"] = self.parse_date(extracted_date)
        
        # Extract client name
        result["client_name"] = self.extract_client_name(message, extracted_info)
        
        # Extract meeting number (but be careful about dates)
        has_date_in_message = extracted_date is not None
        
        if has_date_in_message:
            # If date is present, be very strict - only match explicit "meeting X" or "number X"
            meeting_number_match = re.search(
                r'\b(?:meeting|number)\s+(\d+)(?!\s*(?:st|nd|rd|th|of|january|february|march|april|may|june|july|august|september|october|november|december))',
                message,
                re.IGNORECASE
            )
            if meeting_number_match:
                result["selected_meeting_number"] = int(meeting_number_match.group(1))
        else:
            # No date, can be more lenient
            meeting_number_match = re.search(r'(?:summarize\s+)?(?:meeting\s+)?(?:number\s+)?(\d+)', message, re.IGNORECASE)
            if meeting_number_match:
                # Double-check it's not part of a date
                match_pos = meeting_number_match.start()
                match_end = meeting_number_match.end()
                context_before = message[max(0, match_pos-20):match_pos].lower()
                context_after = message[match_end:min(len(message), match_end+20)].lower()
                months = ['january', 'february', 'march', 'april', 'may', 'june', 'july', 'august', 'september', 'october', 'november', 'december',
                         'jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec']
                date_suffixes = ['st', 'nd', 'rd', 'th']
                
                if not (any(month in context_before for month in months) or any(suffix in context_after for suffix in date_suffixes)):
                    result["selected_meeting_number"] = int(meeting_number_match.group(1))
        
        # Extract meeting ID and calendar event ID from message
        meeting_id_match = re.search(r'meeting\s+id\s+(\d+)', message, re.IGNORECASE)
        if meeting_id_match:
            result["meeting_id"] = int(meeting_id_match.group(1))
        
        calendar_event_match = re.search(r'calendar\s+event\s+([a-zA-Z0-9_\-]+)', message, re.IGNORECASE)
        if calendar_event_match:
            result["calendar_event_id"] = calendar_event_match.group(1)
        
        return result

