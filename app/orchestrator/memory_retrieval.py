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
            # Get user-level memories
            memories = self.memory.get_memory_entries(user_id, client_id=None)
            context["user_memories"] = [
                {"key": m.key, "value": m.value}
                for m in memories
            ]
        
        if client_id:
            # Get client context
            client_context = self.memory.get_client_context(client_id)
            context["client_context"] = client_context
        
        return context

