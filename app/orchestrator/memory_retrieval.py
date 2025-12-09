"""Memory retrieval module."""

from typing import Dict, Any, Optional
from app.memory.repo import MemoryRepository


class MemoryRetriever:
    """Handles memory retrieval for context."""
    
    def __init__(self, memory: MemoryRepository):
        self.memory = memory
    
    async def retrieve(
        self,
        user_id: Optional[int],
        client_id: Optional[int],
        intent: str,
        extracted_info: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Retrieve relevant memory for context."""
        context = {}
        
        if user_id:
            # Get relevant memories based on intent and keywords
            keywords = []
            if extracted_info.get("client_name"):
                keywords.append(extracted_info["client_name"])
            if extracted_info.get("meeting_title"):
                keywords.append(extracted_info["meeting_title"])
            
            memories = self.memory.get_relevant_memories(
                user_id=user_id,
                client_id=client_id,
                intent=intent,
                keywords=keywords if keywords else None,
                limit=10
            )
            context["user_memories"] = [
                {"key": m.key, "value": m.value, "extra_data": m.extra_data}
                for m in memories
            ]
        
        if client_id:
            # Get client context
            client_context = self.memory.get_client_context(client_id)
            context["client_context"] = client_context
        
        return context

