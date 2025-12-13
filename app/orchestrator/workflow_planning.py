"""Workflow planning module."""

import json
import logging
from typing import Dict, Any, Optional
from app.llm.gemini_client import GeminiClient
from app.llm.prompts import WORKFLOW_PLANNING_PROMPT


logger = logging.getLogger(__name__)


VALID_ACTIONS = {
    "find_meeting",
    "retrieve_transcript",
    "retrieve_calendar_event",
    "summarize",
    "generate_followup",
    "generate_brief",
    "resolve_meeting_from_calendar",
    "use_last_selected_meeting",
    "force_summarization",
    "skip_step",
    "ask_user_for_meeting",
}


class WorkflowPlanner:
    """Handles workflow planning based on intent."""
    
    def __init__(self, llm: GeminiClient):
        self.llm = llm
    
    async def plan(
        self,
        intent: str,
        message: str,
        user_id: Optional[int],
        client_id: Optional[int],
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Plan workflow steps based on intent."""
        context_info = f"User ID: {user_id}, Client ID: {client_id}"
        # Read pre-formatted memory context section from context
        memory_context_section = context.get("memory_context_section", "") if context else ""
        if memory_context_section:
            logger.debug(
                "WorkflowPlanner: memory context section available from context",
                extra={
                    "memory_context_length": len(memory_context_section),
                },
            )
        else:
            logger.debug("WorkflowPlanner: no memory context section in context; proceeding without memory")
        
        prompt = f"""Intent: {intent}
User Message: {message}
Context: {context_info}

Plan the workflow and respond in JSON format."""
        if memory_context_section:
            prompt = (
                f"""{prompt}

---
{memory_context_section}
"""
            )
            logger.debug("WorkflowPlanner: applying memory-aware planning context")
        
        try:
            result = self.llm.llm_chat(
                prompt=prompt,
                system_prompt=WORKFLOW_PLANNING_PROMPT,
                response_format="JSON",
                temperature=0.4,
            )

            if isinstance(result, dict):
                plan = result
            elif isinstance(result, str):
                plan = json.loads(result)
            else:
                plan = {"steps": []}

            steps = plan.get("steps", [])
            if isinstance(steps, list):
                for step in steps:
                    if isinstance(step, dict):
                        action = step.get("action")
                        if action not in VALID_ACTIONS:
                            logger.debug(f"Invalid workflow action requested: {action}")
                            step["action"] = "skip_step"

            return plan
        except Exception:
            logger.exception("Workflow planning failed; returning empty plan")
            return {"steps": []}

