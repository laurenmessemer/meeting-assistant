"""Calendar event utility functions."""

from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from app.utils.date_utils import extract_event_datetime


def extract_attendees(event: Dict[str, Any]) -> str:
    """
    Extract attendee names from calendar event.
    
    Args:
        event: Google Calendar event dictionary
    
    Returns:
        Comma-separated string of attendee names, or "Not specified" if none
    """
    if not event:
        return "Not specified"
    
    event_attendees = event.get('attendees', [])
    if not event_attendees:
        return "Not specified"
    
    attendee_names = [
        att.get('displayName') or att.get('email', '')
        for att in event_attendees
        if att.get('displayName') or att.get('email')
    ]
    
    attendees = ", ".join(attendee_names)
    return attendees if attendees else "Not specified"


def sort_events_by_date(events: List[Dict[str, Any]], reverse: bool = True) -> List[Dict[str, Any]]:
    """
    Sort calendar events by date.
    
    Args:
        events: List of calendar event dictionaries
        reverse: If True, sort most recent first (default: True)
    
    Returns:
        Sorted list of events
    """
    if not events:
        return []
    
    def get_event_date(event):
        dt = extract_event_datetime(event)
        if not dt:
            return datetime.min.replace(tzinfo=timezone.utc)
        return dt
    
    return sorted(events, key=get_event_date, reverse=reverse)

