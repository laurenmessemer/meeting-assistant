"""Memory writing module."""

from typing import Optional, Dict, Any
from app.llm.gemini_client import GeminiClient
from app.memory.repo import MemoryRepository
from app.memory.schemas import MemoryEntryCreate
from app.llm.prompts import MEMORY_EXTRACTION_PROMPT


class MemoryWriter:
    """Handles writing information to memory."""
    
    def __init__(self, llm: GeminiClient, memory: MemoryRepository):
        self.llm = llm
        self.memory = memory
    
    async def write(
        self,
        user_id: Optional[int],
        client_id: Optional[int],
        message: str,
        response: str,
        tool_output: Optional[Dict[str, Any]]
    ):
        """Extract and write important information to memory."""
        if not user_id:
            return
        
        # Use LLM to extract memory-worthy information
        prompt = f"""Conversation:
User: {message}
Assistant: {response}

Extract information that should be remembered for future interactions.
Respond in JSON format with key-value pairs."""
        
        try:
            memory_data = self.llm.generate_structured(
                prompt,
                system_prompt=MEMORY_EXTRACTION_PROMPT,
                response_format="JSON",
                temperature=0.3,
            )
            
            if isinstance(memory_data, dict) and memory_data:
                for key, value in memory_data.items():
                    if isinstance(value, (str, int, float, bool)):
                        self.memory.create_or_update_memory_entry(
                            MemoryEntryCreate(
                                user_id=user_id,
                                client_id=client_id,
                                key=key,
                                value=str(value),
                                extra_data={}
                            )
                        )
        except Exception:
            # Silently fail memory extraction
            pass

