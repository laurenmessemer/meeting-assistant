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
        print(f"\n[DEBUG INTENT] IntentRecognizer.recognize() called")
        print(f"   INPUT: message='{message}'")
        
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
                intent_result = result
            elif isinstance(result, str):
                intent_result = json.loads(result)
            else:
                intent_result = {"intent": "general", "confidence": 0.5, "extracted_info": {}}
            
            print(f"   OUTPUT: intent='{intent_result.get('intent')}', confidence={intent_result.get('confidence')}")
            print(f"   OUTPUT: extracted_info={intent_result.get('extracted_info')}")
            print(f"   BRANCH: LLM returned valid result")
            return intent_result
        except Exception as e:
            # Fallback to general intent on error
            print(f"   ❌ ERROR: {str(e)}")
            print(f"   BRANCH: Exception caught, using fallback general intent")
            fallback = {"intent": "general", "confidence": 0.5, "extracted_info": {}}
            print(f"   OUTPUT: {fallback}")
            return fallback

