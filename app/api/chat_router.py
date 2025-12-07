"""Chat API router."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.memory.schemas import ChatMessage, ChatResponse
from app.orchestrator.agent import AgentOrchestrator
from app.memory.repo import MemoryRepository

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
async def chat(
    message: ChatMessage,
    db: Session = Depends(get_db)
):
    """
    Main chat endpoint for interacting with the agent.
    
    The agent will:
    1. Recognize intent
    2. Plan workflow
    3. Retrieve memory
    4. Execute appropriate tool
    5. Synthesize response
    6. Write to memory
    """
    try:
        # Get or create user if user_id not provided
        user_id = message.user_id
        if not user_id and hasattr(message, 'user_email'):
            # In a real app, you'd extract user from auth token
            # For now, we'll use a default or require user_id
            pass
        
        # Initialize orchestrator
        orchestrator = AgentOrchestrator(db)
        
        # Process message
        result = await orchestrator.process_message(
            message=message.message,
            user_id=user_id,
            client_id=message.client_id
        )
        
        return ChatResponse(
            response=result["response"],
            tool_used=result.get("tool_used"),
            extra_data=result.get("metadata", {})
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing message: {str(e)}")
