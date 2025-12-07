"""Main agent orchestrator."""

import json
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session

from app.llm.gemini_client import GeminiClient
from app.llm.prompts import (
    INTENT_RECOGNITION_PROMPT,
    WORKFLOW_PLANNING_PROMPT,
    OUTPUT_SYNTHESIS_PROMPT,
    MEMORY_EXTRACTION_PROMPT,
)
from app.memory.repo import MemoryRepository
from app.memory.schemas import MemoryEntryCreate
from app.tools.summarization import SummarizationTool
from app.tools.meeting_brief import MeetingBriefTool
from app.tools.followup import FollowUpTool


class AgentOrchestrator:
    """Main orchestration pipeline for the agent."""
    
    def __init__(self, db: Session):
        self.db = db
        self.llm = GeminiClient()
        self.memory = MemoryRepository(db)
        self.summarization_tool = SummarizationTool(self.llm, self.memory)
        self.meeting_brief_tool = MeetingBriefTool(self.llm, self.memory)
        self.followup_tool = FollowUpTool(self.llm, self.memory)
    
    async def process_message(
        self,
        message: str,
        user_id: Optional[int] = None,
        client_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Process a user message through the full orchestration pipeline.
        
        Args:
            message: User's message
            user_id: Optional user ID
            client_id: Optional client ID
        
        Returns:
            Dictionary with response and metadata
        """
        # Step 1: Intent Recognition
        intent_data = await self._recognize_intent(message)
        intent = intent_data.get("intent", "general")
        extracted_info = intent_data.get("extracted_info", {})
        
        # Step 2: Workflow Planning
        workflow = await self._plan_workflow(intent, message, user_id, client_id)
        
        # Step 3: Memory Retrieval
        context = await self._retrieve_memory(user_id, client_id, intent, extracted_info)
        
        # Step 4: Tool Execution
        tool_output = await self._execute_tool(
            intent,
            message,
            context,
            user_id,
            client_id,
            extracted_info
        )
        
        # Step 5: Output Synthesis
        response = await self._synthesize_output(
            message,
            intent,
            tool_output,
            context
        )
        
        # Step 6: Memory Writing
        await self._write_memory(user_id, client_id, message, response, tool_output)
        
        return {
            "response": response,
            "tool_used": tool_output.get("tool_name") if tool_output else None,
            "metadata": {
                "intent": intent,
                "confidence": intent_data.get("confidence", 0.0),
                "workflow": workflow,
            }
        }
    
    async def _recognize_intent(self, message: str) -> Dict[str, Any]:
        """Recognize user intent from message."""
        prompt = f"User message: {message}\n\nAnalyze the intent and respond in JSON format."
        
        try:
            result = self.llm.generate_structured(
                prompt,
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
    
    async def _plan_workflow(
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
                return json.loads(result)
            else:
                return {"steps": [], "required_data": [], "estimated_complexity": "medium"}
        except Exception:
            return {"steps": [], "required_data": [], "estimated_complexity": "medium"}
    
    async def _retrieve_memory(
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
    
    async def _execute_tool(
        self,
        intent: str,
        message: str,
        context: Dict[str, Any],
        user_id: Optional[int],
        client_id: Optional[int],
        extracted_info: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Execute the appropriate tool based on intent."""
        try:
            if intent == "meeting_brief":
                # Only execute meeting_brief if there's actual meeting context
                # Check if user mentioned a meeting, date, or client
                has_meeting_context = (
                    extracted_info.get("calendar_event_id") or
                    extracted_info.get("meeting_id") or
                    extracted_info.get("meeting_date") or
                    extracted_info.get("client_name") or
                    any(keyword in message.lower() for keyword in [
                        "meeting", "brief", "prepare", "upcoming", "tomorrow", 
                        "today", "next week", "calendar", "schedule"
                    ])
                )
                
                if not has_meeting_context:
                    # Don't execute tool if no meeting context - treat as general
                    return None
                
                # Extract calendar event ID if mentioned
                calendar_event_id = extracted_info.get("calendar_event_id")
                meeting_id = extracted_info.get("meeting_id")
                client_name = extracted_info.get("client_name")
                
                # Also try to extract client name from message if not in extracted_info
                if not client_name:
                    # Look for patterns like "meeting with X", "meeting with X Corp", etc.
                    import re
                    patterns = [
                        r'meeting with\s+([A-Z][A-Za-z\s]+?)(?:\s|$|,|\.)',
                        r'prepare.*?for.*?meeting.*?with\s+([A-Z][A-Za-z\s]+?)(?:\s|$|,|\.)',
                        r'brief.*?for.*?([A-Z][A-Za-z\s]+?)(?:\s|$|,|\.)',
                    ]
                    for pattern in patterns:
                        match = re.search(pattern, message, re.IGNORECASE)
                        if match:
                            client_name = match.group(1).strip()
                            # Remove common words
                            client_name = re.sub(r'\b(for|with|the|a|an)\b', '', client_name, flags=re.IGNORECASE).strip()
                            if client_name:
                                break
                
                result = await self.meeting_brief_tool.generate_brief(
                    meeting_id=meeting_id,
                    calendar_event_id=calendar_event_id,
                    client_id=client_id,
                    user_id=user_id,
                    client_name=client_name
                )
                return {
                    "tool_name": "meeting_brief",
                    "result": result
                }
            
            elif intent == "summarization":
                meeting_id = extracted_info.get("meeting_id")
                if not meeting_id:
                    # Try to find most recent meeting
                    if client_id:
                        meetings = self.memory.get_meetings_by_client(client_id, limit=1)
                        if meetings:
                            meeting_id = meetings[0].id
                    elif user_id:
                        meetings = self.memory.get_meetings_by_user(user_id, limit=1)
                        if meetings:
                            meeting_id = meetings[0].id
                
                if not meeting_id:
                    return {
                        "tool_name": "summarization",
                        "error": "No meeting found to summarize"
                    }
                
                meeting = self.memory.get_meeting_by_id(meeting_id)
                result = await self.summarization_tool.summarize_meeting(
                    meeting_id=meeting_id,
                    transcript=meeting.transcript if meeting else None,
                    zoom_meeting_id=meeting.zoom_meeting_id if meeting else None
                )
                return {
                    "tool_name": "summarization",
                    "result": result
                }
            
            elif intent == "followup":
                meeting_id = extracted_info.get("meeting_id")
                if not meeting_id and client_id:
                    # Try to find most recent completed meeting
                    meetings = self.memory.get_meetings_by_client(client_id, limit=5)
                    completed_meetings = [m for m in meetings if m.status == "completed"]
                    if completed_meetings:
                        meeting_id = completed_meetings[0].id
                
                result = self.followup_tool.generate_followup_email(
                    meeting_id=meeting_id,
                    client_id=client_id,
                    user_id=user_id,
                    additional_context=extracted_info.get("additional_context")
                )
                return {
                    "tool_name": "followup",
                    "result": result
                }
            
            else:
                # General intent - no specific tool
                return None
        
        except Exception as e:
            return {
                "tool_name": intent,
                "error": str(e)
            }
    
    async def _synthesize_output(
        self,
        message: str,
        intent: str,
        tool_output: Optional[Dict[str, Any]],
        context: Dict[str, Any]
    ) -> str:
        """Synthesize final response from tool outputs."""
        if not tool_output:
            # General response without tool
            prompt = f"""User message: {message}

Provide a helpful response. If the user is asking about meetings, briefs, summaries, or follow-ups, 
guide them on how to use the assistant."""
            
            return self.llm.generate(
                prompt,
                system_prompt=OUTPUT_SYNTHESIS_PROMPT,
                temperature=0.7,
            )
        
        # Synthesize from tool output
        tool_name = tool_output.get("tool_name")
        tool_result = tool_output.get("result")
        tool_error = tool_output.get("error")
        
        if tool_error:
            # Provide more helpful error messages
            if "No meeting information available" in tool_error:
                return (
                    "I couldn't find any meeting information. This could be because:\n"
                    "- Your Google Calendar isn't connected yet (you'll need to authenticate on first use)\n"
                    "- There are no upcoming meetings in your calendar\n"
                    "- You haven't specified a specific meeting\n\n"
                    "Try asking: 'What meetings do I have coming up?' or 'Prepare me for my meeting tomorrow'"
                )
            elif "Error getting Google" in tool_error or "credentials" in tool_error.lower():
                return (
                    "I need to connect to your Google Calendar to help with meetings. "
                    "Please authenticate with Google when prompted. "
                    "You can also try asking general questions that don't require calendar access."
                )
            else:
                return f"I encountered an error: {tool_error}. Please try again or provide more context."
        
        if tool_name == "meeting_brief":
            brief = tool_result.get("brief", "")
            return brief
        
        elif tool_name == "summarization":
            summary = tool_result.get("summary", "")
            decisions = tool_result.get("decisions", [])
            actions = tool_result.get("actions", [])
            
            response_parts = [summary]
            
            if decisions:
                response_parts.append("\n\nDecisions Made:")
                for d in decisions:
                    response_parts.append(f"- {d.get('description', '')}")
            
            if actions:
                response_parts.append("\n\nAction Items:")
                for a in actions:
                    assignee_text = f" ({a.get('assignee')})" if a.get('assignee') else ""
                    due_text = f" by {a.get('due_date')}" if a.get('due_date') else ""
                    response_parts.append(f"- {a.get('description', '')}{assignee_text}{due_text}")
            
            return "\n".join(response_parts)
        
        elif tool_name == "followup":
            email_body = tool_result.get("body", "")
            subject = tool_result.get("subject", "")
            
            return f"Subject: {subject}\n\n{email_body}"
        
        else:
            return "I've processed your request. Here's the result."
    
    async def _write_memory(
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

