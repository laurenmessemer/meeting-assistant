"""Workflow planning module."""

from typing import Dict, Any, Optional
from app.llm.gemini_client import GeminiClient
from app.llm.prompts import WORKFLOW_PLANNING_PROMPT


class WorkflowPlanner:
    """Handles workflow planning based on intent."""
    
    def __init__(self, llm: GeminiClient):
        self.llm = llm
    
    async def plan(
        self,
        intent: str,
        message: str,
        user_id: Optional[int],
        client_id: Optional[int]
    ) -> Dict[str, Any]:
        """Plan workflow steps based on intent."""
        context_info = f"User ID: {user_id}, Client ID: {client_id}"
        
        prompt = f"""Intent: {intent}
User Message: {message}
Context: {context_info}

Plan the workflow and respond in JSON format."""
        
        try:
            result = self.llm.generate_structured(
                prompt,
                system_prompt=WORKFLOW_PLANNING_PROMPT,
                response_format="JSON",
                temperature=0.4,
            )
            
            if isinstance(result, dict):
                return result
            elif isinstance(result, str):
                import json
                return json.loads(result)
            else:
                return {"steps": []}
        except Exception:
            return {"steps": []}

