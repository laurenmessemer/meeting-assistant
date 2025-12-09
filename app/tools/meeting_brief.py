"""Meeting brief tool for pre-meeting preparation."""

from typing import Dict, Any, Optional, List
from app.llm.gemini_client import GeminiClient
from app.llm.prompts import SUMMARIZATION_TOOL_PROMPT
from app.tools.memory_processing import synthesize_memory


class MeetingBriefTool:
    """Tool for generating meeting briefs."""
    
    def __init__(self, llm_client: GeminiClient):
        self.llm = llm_client
    
    async def generate_brief(
        self,
        client_name: Optional[str] = None,
        meeting_title: Optional[str] = None,
        meeting_date: Optional[str] = None,
        attendees: Optional[str] = None,
        previous_meeting_summary: Optional[str] = None,
        client_context: Optional[str] = None,
        past_context: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Generate a meeting brief.
        
        Args:
            client_name: Client name
            meeting_title: Meeting title
            meeting_date: Meeting date/time
            attendees: Comma-separated list of attendees
            previous_meeting_summary: Optional summary of previous meeting for context
            client_context: Optional client context/information
            past_context: Optional list of past meeting memories for context
        
        Returns:
            Dictionary with brief content
        """
        # Synthesize memory insights if past_context provided
        insights = {
            "communication_style": "",
            "client_history": "",
            "recurring_topics": "",
            "open_loops": "",
            "preferences": ""
        }
        if past_context:
            try:
                insights = await synthesize_memory(past_context, self.llm)
            except Exception:
                # Fail gracefully - continue without memory insights
                pass
        
        # Build memory context section if insights exist
        memory_context_section = ""
        if any(insights.values()):  # Only include if at least one field has content
            memory_context_section = f"""
Context From Prior Meetings:
- Communication style: {insights['communication_style']}
- Client history: {insights['client_history']}
- Recurring themes: {insights['recurring_topics']}
- Open loops: {insights['open_loops']}
- User preferences: {insights['preferences']}
"""
            # Enforce 1200 character limit on memory context section
            if len(memory_context_section) > 1200:
                memory_context_section = memory_context_section[:1200] + "..."
        
        # Build prompt for meeting brief
        context_parts = []
        
        if client_name:
            context_parts.append(f"Client: {client_name}")
        if meeting_title:
            context_parts.append(f"Meeting Title: {meeting_title}")
        if meeting_date:
            context_parts.append(f"Meeting Date: {meeting_date}")
        if attendees:
            context_parts.append(f"Attendees: {attendees}")
        if client_context:
            context_parts.append(f"\nClient Context:\n{client_context}")
        if previous_meeting_summary:
            context_parts.append(f"\nPrevious Meeting Summary:\n{previous_meeting_summary}")
        
        if memory_context_section:
            context_parts.append(memory_context_section)
        
        prompt = f"""Generate a comprehensive meeting brief to help prepare for an upcoming meeting.

Meeting Information:
{chr(10).join(context_parts) if context_parts else "No specific meeting information provided."}

Please create a meeting brief that includes:
1. Key topics to discuss
2. Important context about the client
3. Questions to ask
4. Goals and objectives
5. Any relevant background information

Format the brief in a clear, organized structure that will help prepare for the meeting."""
        
        brief_text = self.llm.llm_chat(
            prompt=prompt,
            system_prompt=SUMMARIZATION_TOOL_PROMPT,
            response_format="text",
            temperature=0.7,
        )
        
        return {
            "brief": brief_text,
            "client_name": client_name,
            "meeting_title": meeting_title,
            "meeting_date": meeting_date,
            "attendees": attendees
        }
