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
            
            return self.llm.llm_chat(
                prompt=prompt,
                system_prompt=OUTPUT_SYNTHESIS_PROMPT,
                response_format="text",
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
            # Get structured summary data - the summary_text already contains the full structured format
            summary_text = tool_result.get("summary", "")
            
            # DIAGNOSTIC: Log incoming summarization payload
            print(f"\n[DIAGNOSTIC SYNTHESIS] synthesize() - SUMMARIZATION")
            print(f"   incoming summarization payload:")
            print(f"      summary_length: {len(summary_text)} characters")
            print(f"      summary_preview (first 300 chars): {summary_text[:300] if summary_text else 'N/A'}...")
            print(f"      tool_result keys: {list(tool_result.keys())}")
            print(f"      meeting_title: '{tool_result.get('meeting_title', 'N/A')}'")
            print(f"      meeting_date: '{tool_result.get('meeting_date', 'N/A')}'")
            print(f"      attendees: '{tool_result.get('attendees', 'N/A')}'")
            
            # DIAGNOSTIC: Try to infer client_name from summary or context
            inferred_client = None
            if summary_text:
                # Try to extract client name from summary text (look for common patterns)
                import re
                # Look for patterns like "MTCA", "Good Health", etc. in the summary
                client_patterns = [
                    r'\b(MTCA|Good Health|IBM|Microsoft)\b',  # Common client names
                ]
                for pattern in client_patterns:
                    match = re.search(pattern, summary_text, re.IGNORECASE)
                    if match:
                        inferred_client = match.group(1)
                        break
            
            # Also check context for client_name
            context_client = context.get("client_name") or context.get("extracted_info", {}).get("client_name")
            system_client = context_client or inferred_client
            
            print(f"   system thinks meeting belongs to client: '{system_client}'")
            print(f"      (inferred from summary: '{inferred_client}', from context: '{context_client}')")
            
            # DIAGNOSTIC: Log pipeline branch
            print(f"   pipeline branch: general (summarization tool output returned directly)")
            
            # The summary_text from summarization tool already includes:
            # - Meeting Header (title)
            # - Date from calendar
            # - Participants
            # - Overview
            # - Outline
            # - Action Items (for Client and User)
            # - Conclusion
            # So we can return it directly for the UI to format
            
            # DIAGNOSTIC: Log final returned content
            final_preview = summary_text[:500] + "..." if len(summary_text) > 500 else summary_text
            print(f"   final synthesized summary (returned to frontend):")
            print(f"      length: {len(summary_text)} characters")
            print(f"      preview (first 500 chars): {final_preview}")
            
            return summary_text
        
        elif tool_name == "followup":
            email_body = tool_result.get("body", "")
            subject = tool_result.get("subject", "")
            
            return f"Subject: {subject}\n\n{email_body}"
        
        else:
            return "I've processed your request. Here's the result."

