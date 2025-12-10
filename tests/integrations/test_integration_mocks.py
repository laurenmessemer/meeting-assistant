"""Mock utilities and builder functions for test suite."""

from typing import Dict, Any, Optional, List
from unittest.mock import MagicMock
from datetime import datetime


def build_mock_workflow(
    steps: Optional[List[Any]] = None,
    required_data: Optional[List[str]] = None,
    fallbacks: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """Build a mock workflow structure."""
    workflow = {"steps": steps or []}
    if required_data:
        workflow["required_data"] = required_data
    return workflow


def build_mock_step(
    action: str,
    tool: str,
    prerequisites: Optional[List[str]] = None,
    fallback: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Build a mock step dict."""
    step = {"action": action, "tool": tool}
    if prerequisites:
        step["prerequisites"] = prerequisites
    if fallback:
        step["fallback"] = fallback
    return step


def build_mock_fallback(
    action: str,
    conditions: Optional[List[str]] = None,
    max_attempts: int = 1,
    message_to_user: Optional[str] = None
) -> Dict[str, Any]:
    """Build a mock fallback dict."""
    fallback = {"action": action}
    if conditions:
        fallback["conditions"] = conditions
    if max_attempts:
        fallback["max_attempts"] = max_attempts
    if message_to_user:
        fallback["message_to_user"] = message_to_user
    return fallback


def build_mock_context(
    user_memories: Optional[List[Dict[str, Any]]] = None,
    client_context: Optional[Dict[str, Any]] = None,
    persistent_memory: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Build a mock context dict."""
    context = {}
    if user_memories:
        context["user_memories"] = user_memories
    if client_context:
        context["client_context"] = client_context
    if persistent_memory:
        context["persistent_memory"] = persistent_memory
    return context


def build_mock_prepared_data(
    meeting_id: Optional[int] = None,
    client_id: Optional[int] = None,
    client_name: Optional[str] = None,
    target_date: Optional[datetime] = None,
    calendar_event_id: Optional[str] = None
) -> Dict[str, Any]:
    """Build a mock prepared_data dict."""
    data = {}
    if meeting_id:
        data["meeting_id"] = meeting_id
    if client_id:
        data["client_id"] = client_id
    if client_name:
        data["client_name"] = client_name
    if target_date:
        data["target_date"] = target_date
    if calendar_event_id:
        data["calendar_event_id"] = calendar_event_id
    return data


def build_mock_integration_data(
    meeting_id: Optional[int] = None,
    calendar_event: Optional[Dict[str, Any]] = None,
    structured_data: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Build a mock integration_data dict."""
    data = {}
    if meeting_id:
        data["meeting_id"] = meeting_id
    if calendar_event:
        data["calendar_event"] = calendar_event
    if structured_data:
        data["structured_data"] = structured_data
    else:
        data["structured_data"] = {}
    return data


def build_mock_meeting(
    id: int = 1,
    title: str = "Test Meeting",
    date: Optional[datetime] = None,
    transcript: Optional[str] = None,
    summary: Optional[str] = None,
    client_id: Optional[int] = None,
    attendees: Optional[str] = None
) -> MagicMock:
    """Build a mock meeting object."""
    meeting = MagicMock()
    meeting.id = id
    meeting.title = title
    meeting.scheduled_time = date or datetime(2024, 5, 1, 10, 0, 0)
    meeting.transcript = transcript
    meeting.summary = summary
    meeting.client_id = client_id
    meeting.attendees = attendees
    meeting.has_transcript = transcript is not None
    return meeting


def build_mock_calendar_event(
    id: str = "test_event_123",
    summary: str = "Test Event",
    start: Optional[Dict[str, str]] = None,
    attendees: Optional[List[Dict[str, str]]] = None
) -> Dict[str, Any]:
    """Build a mock calendar event dict."""
    event = {
        "id": id,
        "summary": summary,
        "start": start or {"dateTime": "2024-05-01T10:00:00Z"}
    }
    if attendees:
        event["attendees"] = attendees
    return event


def build_mock_transcript(text: str = "Test transcript content") -> str:
    """Build a mock transcript string."""
    return text


def build_mock_llm_response(
    intent: Optional[str] = None,
    workflow: Optional[Dict[str, Any]] = None,
    tool_output: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Build a mock LLM response."""
    if intent:
        return {"intent": intent, "confidence": 0.95, "extracted_info": {}}
    if workflow:
        return workflow
    if tool_output:
        return tool_output
    return {}


def simulate_llm_call_sequence(call_sequence: List[Any]):
    """Simulate a sequence of LLM calls."""
    call_index = [0]
    def side_effect(*args, **kwargs):
        if call_index[0] >= len(call_sequence):
            return call_sequence[-1]  # Return last value if out of bounds
        result = call_sequence[call_index[0]]
        call_index[0] += 1
        return result
    return side_effect


def inject_error(mock: MagicMock, error_type: type, error_message: str):
    """Inject error into mock."""
    mock.side_effect = error_type(error_message)

