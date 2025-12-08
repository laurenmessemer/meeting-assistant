"""Output synthesis module."""

from typing import Optional, Dict, Any
from app.llm.gemini_client import GeminiClient
from app.llm.prompts import OUTPUT_SYNTHESIS_PROMPT


class OutputSynthesizer:
    """Handles output synthesis from tool results."""
    
    def __init__(self, llm: GeminiClient):
        self.llm = llm
    
    async def synthesize(
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
        requires_selection = tool_output.get("requires_selection", False)
        meeting_options = tool_output.get("meeting_options")
        
        # If meeting selection is required, return a formatted list
        if requires_selection and meeting_options:
            response_parts = [
                f"I found {len(meeting_options)} meeting(s) matching your request. Please select which one you'd like me to summarize:\n\n"
            ]
            for i, option in enumerate(meeting_options, 1):
                # Handle both dict and object formats
                if isinstance(option, dict):
                    title = option.get("title", "Untitled")
                    date = option.get("date", "Unknown date")
                    client_name = option.get("client_name", "")
                else:
                    title = getattr(option, 'title', 'Untitled')
                    date = getattr(option, 'date', 'Unknown date')
                    client_name = getattr(option, 'client_name', '')
                
                response_parts.append(f"{i}. {title}")
                response_parts.append(f"   Date: {date}")
                if client_name:
                    response_parts.append(f"   Client: {client_name}")
                response_parts.append("")
            response_parts.append("Reply with the number (1, 2, 3, etc.) or the meeting title.")
            return "\n".join(response_parts)
        
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
            elif "Error getting Google" in tool_error or ("credentials" in tool_error.lower() and "google" in tool_error.lower()):
                return (
                    "I need to connect to your Google Calendar to help with meetings. "
                    "Please authenticate with Google when prompted. "
                    "You can also try asking general questions that don't require calendar access.\n\n"
                    f"Technical details: {tool_error}"
                )
            else:
                return f"I encountered an error: {tool_error}. Please try again or provide more context."
        
        if tool_name == "meeting_brief":
            brief = tool_result.get("brief", "")
            return brief
        
        elif tool_name == "summarization":
            # Get structured summary data
            summary_text = tool_result.get("summary", "")
            meeting_title = tool_result.get("meeting_title", "Untitled Meeting")
            meeting_date = tool_result.get("meeting_date", "Unknown date")
            recording_date = tool_result.get("recording_date", None)
            attendees = tool_result.get("attendees", "Not specified")
            decisions = tool_result.get("decisions", [])
            actions = tool_result.get("actions", [])
            
            # Format structured summary response
            response_parts = [
                "## Summary\n",
                f"**Meeting Title:** {meeting_title}\n",
                f"**Calendar Event Date:** {meeting_date}\n"
            ]
            
            # Add recording date if available
            if recording_date:
                response_parts.append(f"**Zoom Recording Date:** {recording_date}\n")
            
            response_parts.extend([
                f"**Attendees:** {attendees}\n\n",
                summary_text
            ])
            
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

