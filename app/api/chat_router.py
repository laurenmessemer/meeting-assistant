"""Basic chat API router (1-hour scope)."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.session import get_db
from pydantic import BaseModel

router = APIRouter(prefix="/api/chat", tags=["chat"])


class ChatMessage(BaseModel):
    """Chat message request."""
    message: str
    user_id: int = None


class ChatResponse(BaseModel):
    """Chat response."""
    response: str


@router.post("", response_model=ChatResponse)
async def chat(
    message: ChatMessage,
    db: Session = Depends(get_db)
):
    """
    Basic chat endpoint (1-hour scope).
    Simple echo response - would integrate with HubSpot/LLM in full version.
    """
    try:
        # Basic response (in full version, this would use orchestrator + LLM)
        response_text = f"Received: {message.message}. [Basic endpoint - full AI integration would go here]"
        
        return ChatResponse(response=response_text)
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing message: {str(e)}")

