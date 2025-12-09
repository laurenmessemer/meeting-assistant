"""Date and time utility functions."""

from typing import Optional, Dict, Any
from datetime import datetime, timezone


def parse_iso_datetime(date_str: str, default_tz: timezone = timezone.utc) -> Optional[datetime]:
    """
    Parse ISO format datetime string with timezone handling.
    
    Handles:
    - ISO format with timezone: "2024-11-21T10:00:00Z" or "2024-11-21T10:00:00+00:00"
    - ISO format without timezone: "2024-11-21T10:00:00"
    - Date only: "2024-11-21"
    
    Args:
        date_str: ISO format datetime string
        default_tz: Timezone to use if none is specified (default: UTC)
    
    Returns:
        Parsed datetime object with timezone, or None if parsing fails
    """
    if not date_str:
        return None
    
    try:
        if 'T' in date_str:
            # Has time component
            dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        else:
            # Date only
            dt = datetime.fromisoformat(date_str)
        
        # Ensure timezone is set
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=default_tz)
        else:
            dt = dt.astimezone(default_tz)
        
        return dt
    except (ValueError, AttributeError, TypeError):
        return None


def format_datetime_display(dt: Optional[datetime], default: str = "Unknown date") -> str:
    """
    Format datetime to human-readable display string.
    
    Format: "November 21, 2024 at 10:00 AM"
    
    Args:
        dt: Datetime object to format
        default: Default string to return if dt is None or formatting fails
    
    Returns:
        Formatted date string
    """
    if not dt:
        return default
    
    try:
        return dt.strftime("%B %d, %Y at %I:%M %p")
    except (AttributeError, ValueError, TypeError):
        return default


def extract_event_datetime(event: Dict[str, Any]) -> Optional[datetime]:
    """
    Extract datetime from Google Calendar event.
    
    Args:
        event: Google Calendar event dictionary
    
    Returns:
        Parsed datetime object or None if extraction fails
    """
    if not event:
        return None
    
    event_start = event.get('start', {})
    if not event_start:
        return None
    
    start_time_str = event_start.get('dateTime') or event_start.get('date')
    if not start_time_str:
        return None
    
    return parse_iso_datetime(start_time_str)

