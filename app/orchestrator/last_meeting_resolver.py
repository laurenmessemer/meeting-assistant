"""Last meeting auto-resolution module.

Auto-selects the most recent calendar event when user explicitly requests
"last meeting" and multiple options exist.
"""

from typing import Optional, Dict, Any, List
from app.integrations.google_calendar_client import get_calendar_event_by_id


def resolve_last_meeting(
    message: str,
    intent: str,
    target_date: Optional[Any],
    meeting_options: Optional[List[Any]]
) -> Optional[Dict[str, Any]]:
    """
    Auto-resolve "last meeting" requests by selecting the most recent calendar event.
    
    Only auto-selects when ALL of the following conditions are met:
    1. intent is "summarize_meeting" or "summarization"
    2. target_date is None (no specific date provided)
    3. meeting_options exist and has multiple items
    4. user message contains recency language ("last", "latest", "most recent")
    
    Args:
        message: Original user message (to detect recency language)
        intent: Detected intent (must be summarization-related)
        target_date: Target date from prepared_data (must be None for auto-resolution)
        meeting_options: List of MeetingOption objects (must have multiple items)
    
    Returns:
        Calendar event dict if auto-resolution applies, None otherwise
    """
    # Condition 1: Intent must be summarization
    if intent not in ("summarize_meeting", "summarization"):
        return None
    
    # Condition 2: No target date provided
    if target_date is not None:
        return None
    
    # Condition 3: Multiple meeting options must exist
    if not meeting_options or not isinstance(meeting_options, list):
        return None
    
    if len(meeting_options) < 2:
        return None
    
    # Condition 4: Message must contain recency language
    message_lower = message.lower() if message else ""
    recency_keywords = ["last", "latest", "most recent", "most-recent"]
    has_recency_language = any(keyword in message_lower for keyword in recency_keywords)
    
    if not has_recency_language:
        return None
    
    # All conditions met - auto-select the first (most recent) option
    first_option = meeting_options[0]
    
    # Extract calendar_event_id from MeetingOption
    # Handle both dict and Pydantic model
    if isinstance(first_option, dict):
        calendar_event_id = first_option.get("calendar_event_id")
    else:
        calendar_event_id = getattr(first_option, "calendar_event_id", None)
    
    if not calendar_event_id:
        return None
    
    # Fetch the actual calendar event
    try:
        calendar_event = get_calendar_event_by_id(calendar_event_id)
        return calendar_event
    except Exception:
        # If fetching fails, return None (don't auto-resolve)
        return None

