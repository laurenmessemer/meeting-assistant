"""Chat API router."""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from app.db.session import get_db
from app.orchestrator.agent import AgentOrchestrator
from sqlalchemy.orm import Session


router = APIRouter(prefix="/api", tags=["chat"])


class ChatMessage(BaseModel):
    """Chat message request model."""
    message: str
    user_id: Optional[int] = None
    client_id: Optional[int] = None
    selected_meeting_id: Optional[int] = None
    selected_calendar_event_id: Optional[str] = None


class MeetingOption(BaseModel):
    """Meeting option for user selection."""
    id: str
    title: str
    date: str
    calendar_event_id: Optional[str] = None
    meeting_id: Optional[int] = None
    client_name: Optional[str] = None


class ChatResponse(BaseModel):
    """Chat response model."""
    response: str
    tool_used: Optional[str] = None
    meeting_options: Optional[List[MeetingOption]] = None
    extra_data: Optional[Dict[str, Any]] = None


@router.post("/chat", response_model=ChatResponse)
async def chat(
    chat_message: ChatMessage,
    db: Session = Depends(get_db),
    debug: bool = Query(False, description="Include intermediate outputs in response (development only)")
):
    """
    Process a chat message and return a response.
    
    Args:
        chat_message: Chat message request
        db: Database session
        debug: If True, include intermediate outputs in response (development only)
    """
    try:
        orchestrator = AgentOrchestrator(db)
        
        result = await orchestrator.process_message(
            message=chat_message.message,
            user_id=chat_message.user_id,
            client_id=chat_message.client_id,
            selected_meeting_id=chat_message.selected_meeting_id,
            selected_calendar_event_id=chat_message.selected_calendar_event_id,
            debug=debug
        )
        
        # Convert meeting_options to MeetingOption models if present
        meeting_options = None
        if result.get("meeting_options"):
            meeting_options = [
                MeetingOption(**opt) if isinstance(opt, dict) else opt
                for opt in result["meeting_options"]
            ]
        
        # Prepare extra_data with metadata
        extra_data = result.get("metadata", {})
        if debug and "debug" in result:
            extra_data["debug"] = result["debug"]
        
        return ChatResponse(
            response=result.get("response", ""),
            tool_used=result.get("tool_used"),
            meeting_options=meeting_options,
            extra_data=extra_data
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing message: {str(e)}")

