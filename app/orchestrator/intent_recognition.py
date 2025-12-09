"""Intent recognition module."""

import json
from typing import Dict, Any
from app.llm.gemini_client import GeminiClient
from app.llm.prompts import INTENT_RECOGNITION_PROMPT


class IntentRecognizer:
    """Handles intent recognition from user messages."""
    
    def __init__(self, llm: GeminiClient):
        self.llm = llm
    
    async def recognize(self, message: str) -> Dict[str, Any]:
        """Recognize user intent from message."""
        prompt = f"User message: {message}\n\nAnalyze the intent and respond in JSON format."
        
        try:
            result = self.llm.llm_chat(
                prompt=prompt,
                system_prompt=INTENT_RECOGNITION_PROMPT,
                response_format="JSON",
                temperature=0.3,
            )
            
            # Handle both dict and string responses
            if isinstance(result, dict):
                return result
            elif isinstance(result, str):
                return json.loads(result)
            else:
                return {"intent": "general", "confidence": 0.5, "extracted_info": {}}
        except Exception as e:
            # Fallback to general intent on error
            return {"intent": "general", "confidence": 0.5, "extracted_info": {}}

