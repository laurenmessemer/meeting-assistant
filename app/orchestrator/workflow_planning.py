"""Workflow planning module."""

import json
import logging
from typing import Dict, Any, Optional
from app.llm.gemini_client import GeminiClient
from app.llm.prompts import WORKFLOW_PLANNING_PROMPT
from app.tools.memory_processing import synthesize_memory


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
        memory_insights = None
        if context and isinstance(context.get("user_memories"), list) and context.get("user_memories"):
            past_context = context.get("user_memories")[:5]
            try:
                memory_insights = await synthesize_memory(past_context, self.llm)
                logger.debug(
                    "WorkflowPlanner: memory insights computed",
                    extra={
                        "user_memories_used": len(past_context),
                        "insights_keys": list(memory_insights.keys()) if isinstance(memory_insights, dict) else [],
                    },
                )
            except Exception:
                memory_insights = None
                logger.debug(
                    "WorkflowPlanner: memory insights unavailable; proceeding without memory",
                    exc_info=True,
                )
        else:
            logger.debug("WorkflowPlanner: no memory context provided; proceeding without memory")
        
        prompt = f"""Intent: {intent}
User Message: {message}
Context: {context_info}

Plan the workflow and respond in JSON format."""
        if isinstance(memory_insights, dict):
            prompt = (
                f"""{prompt}

---
User Context / Memory (optional):
- Communication style: {memory_insights.get('communication_style', '')}
- Preferences: {memory_insights.get('preferences', '')}
- Recurring topics: {memory_insights.get('recurring_topics', '')}
- Open loops: {memory_insights.get('open_loops', '')}
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

