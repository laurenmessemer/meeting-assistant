"""Google Calendar client."""

from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from googleapiclient.discovery import build
from app.integrations.google_auth import get_google_credentials


class GoogleCalendarClient:
    """Client for interacting with Google Calendar API."""
    
    def __init__(self):
        creds = get_google_credentials()
        self.service = build('calendar', 'v3', credentials=creds)
    
    def get_upcoming_events(self, max_results: int = 10, time_min: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """
        Get upcoming calendar events.
        
        Args:
            max_results: Maximum number of events to return
            time_min: Start time for events (defaults to now)
        
        Returns:
            List of event dictionaries
        """
        if time_min is None:
            time_min = datetime.utcnow()
        
        try:
            events_result = self.service.events().list(
                calendarId='primary',
                timeMin=time_min.isoformat() + 'Z',
                maxResults=max_results,
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            
            events = events_result.get('items', [])
            return events
        except Exception as e:
            raise Exception(f"Error fetching calendar events: {str(e)}")
    
    def get_event_by_id(self, event_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a specific calendar event by ID.
        
        Args:
            event_id: Google Calendar event ID
        
        Returns:
            Event dictionary or None if not found
        """
        try:
            event = self.service.events().get(
                calendarId='primary',
                eventId=event_id
            ).execute()
            return event
        except Exception as e:
            raise Exception(f"Error fetching event: {str(e)}")
    
    def get_events_by_time_range(
        self, 
        start_time: datetime, 
        end_time: datetime
    ) -> List[Dict[str, Any]]:
        """
        Get events within a specific time range.
        
        Args:
            start_time: Start of time range
            end_time: End of time range
        
        Returns:
            List of event dictionaries
        """
        try:
            events_result = self.service.events().list(
                calendarId='primary',
                timeMin=start_time.isoformat() + 'Z',
                timeMax=end_time.isoformat() + 'Z',
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            
            events = events_result.get('items', [])
            return events
        except Exception as e:
            raise Exception(f"Error fetching calendar events: {str(e)}")
    
    def get_event_attendees(self, event_id: str) -> List[Dict[str, Any]]:
        """
        Get attendees for a specific event.
        
        Args:
            event_id: Google Calendar event ID
        
        Returns:
            List of attendee dictionaries
        """
        event = self.get_event_by_id(event_id)
        if event:
            return event.get('attendees', [])
        return []
    
    def search_events_by_keyword(self, keyword: str, max_results: int = 10) -> List[Dict[str, Any]]:
        """
        Search for calendar events containing a keyword in title or description.
        
        Args:
            keyword: Keyword to search for (e.g., client name)
            max_results: Maximum number of results to return
        
        Returns:
            List of event dictionaries matching the keyword
        """
        try:
            # Get upcoming events and filter by keyword
            time_min = datetime.utcnow()
            # Search up to 30 days in the future
            time_max = time_min + timedelta(days=30)
            
            events_result = self.service.events().list(
                calendarId='primary',
                timeMin=time_min.isoformat() + 'Z',
                timeMax=time_max.isoformat() + 'Z',
                maxResults=50,  # Get more to filter
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            
            events = events_result.get('items', [])
            
            # Filter events that contain the keyword
            keyword_lower = keyword.lower()
            matching_events = []
            for event in events:
                title = event.get('summary', '').lower()
                description = event.get('description', '').lower()
                location = event.get('location', '').lower()
                
                if (keyword_lower in title or 
                    keyword_lower in description or 
                    keyword_lower in location):
                    matching_events.append(event)
                    if len(matching_events) >= max_results:
                        break
            
            return matching_events
        except Exception as e:
            raise Exception(f"Error searching calendar events: {str(e)}")
    
    def extract_meeting_info(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract relevant meeting information from a calendar event.
        
        Args:
            event: Google Calendar event dictionary
        
        Returns:
            Structured meeting information
        """
        start = event.get('start', {})
        end = event.get('end', {})
        
        start_time = start.get('dateTime') or start.get('date')
        end_time = end.get('dateTime') or end.get('date')
        
        return {
            'id': event.get('id'),
            'title': event.get('summary', 'No Title'),
            'description': event.get('description', ''),
            'start_time': start_time,
            'end_time': end_time,
            'location': event.get('location', ''),
            'attendees': [
                {
                    'email': att.get('email'),
                    'name': att.get('displayName'),
                    'response_status': att.get('responseStatus')
                }
                for att in event.get('attendees', [])
            ],
            'organizer': {
                'email': event.get('organizer', {}).get('email'),
                'name': event.get('organizer', {}).get('displayName')
            },
            'hangout_link': event.get('hangoutLink'),
            'conference_data': event.get('conferenceData', {})
        }

