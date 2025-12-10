"""Output synthesis module."""

import logging
from typing import Optional, Dict, Any
from app.llm.gemini_client import GeminiClient
from app.llm.prompts import OUTPUT_SYNTHESIS_PROMPT
from app.tools.memory_processing import synthesize_memory


logger = logging.getLogger(__name__)


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
        # Derive memory insights (optional, best-effort)
        memory_insights = None
        past_context = None
        try:
            if context and isinstance(context.get("user_memories"), list) and context.get("user_memories"):
                past_context = context.get("user_memories")[:5]
                memory_insights = await synthesize_memory(past_context, self.llm)
                logger.debug(
                    "Output synthesis memory insights computed",
                    extra={
                        "memory_available": True,
                        "user_memories_used": len(past_context),
                        "insights_keys": list(memory_insights.keys()) if isinstance(memory_insights, dict) else []
                    }
                )
            else:
                logger.debug(
                    "Output synthesis memory insights skipped",
                    extra={"memory_available": False}
                )
        except Exception:
            memory_insights = None
            logger.debug(
                "Output synthesis memory insights failed; falling back to default behavior",
                exc_info=True
            )

        if not tool_output:
            # General response without tool
            if memory_insights:
                prompt = f"""User message: {message}

User Context / Memory:
- Communication style: {memory_insights.get('communication_style', '')}
- Preferences: {memory_insights.get('preferences', '')}
- Recurring topics: {memory_insights.get('recurring_topics', '')}
- Open loops: {memory_insights.get('open_loops', '')}

Provide a helpful response. If the user is asking about meetings, briefs, summaries, or follow-ups, 
guide them on how to use the assistant."""
                logger.debug("Applying memory-aware synthesis in general branch")
            else:
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
        
        # If meeting selection is required, return a formatted list (unchanged; memory-aware logic does not apply here)
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
            if memory_insights:
                try:
                    prompt = f"""You are personalizing a meeting brief to match the user's communication style and preferences.

Original Brief:
{brief}

User Context / Memory:
- Communication style: {memory_insights.get('communication_style', '')}
- Preferences: {memory_insights.get('preferences', '')}
- Recurring topics: {memory_insights.get('recurring_topics', '')}
- Open loops: {memory_insights.get('open_loops', '')}

Rephrase the brief to align with the user's style and preferences while preserving all factual content.
Do not add new facts. Return only the rephrased brief."""
                    personalized_brief = self.llm.llm_chat(
                        prompt=prompt,
                        system_prompt=OUTPUT_SYNTHESIS_PROMPT,
                        response_format="text",
                        temperature=0.7,
                    )
                    logger.debug("Applied memory-aware synthesis for meeting_brief")
                    return personalized_brief
                except Exception:
                    logger.debug(
                        "Memory-aware synthesis failed for meeting_brief; returning original brief",
                        exc_info=True
                    )
            return brief
        
        elif tool_name == "summarization":
            # Get structured summary data - the summary_text already contains the full structured format
            summary_text = tool_result.get("summary", "")
            
            # DIAGNOSTIC: Log incoming summarization payload
            logger.debug(
                "[DIAGNOSTIC SYNTHESIS] synthesize() - SUMMARIZATION",
                extra={
                    "summary_length": len(summary_text),
                    "summary_preview": summary_text[:300] if summary_text else "N/A",
                    "tool_result_keys": list(tool_result.keys()) if tool_result else [],
                    "meeting_title": tool_result.get("meeting_title", "N/A"),
                    "meeting_date": tool_result.get("meeting_date", "N/A"),
                    "attendees": tool_result.get("attendees", "N/A"),
                },
            )
            
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
            
            logger.debug(
                "System client inference for summarization",
                extra={
                    "system_client": system_client,
                    "inferred_client": inferred_client,
                    "context_client": context_client,
                    "pipeline_branch": "general (summarization tool output returned directly)",
                },
            )
            
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
            logger.debug(
                "Final synthesized summary (returned to frontend)",
                extra={
                    "length": len(summary_text),
                    "preview": final_preview,
                },
            )
            
            if memory_insights:
                try:
                    prompt = f"""You are personalizing a meeting summary to match the user's communication style and preferences.

Original Summary:
{summary_text}

User Context / Memory:
- Communication style: {memory_insights.get('communication_style', '')}
- Preferences: {memory_insights.get('preferences', '')}
- Recurring topics: {memory_insights.get('recurring_topics', '')}
- Open loops: {memory_insights.get('open_loops', '')}

Rephrase the summary to align with the user's style and preferences while preserving all factual content.
Do not add new facts. Return only the rephrased summary."""
                    personalized_summary = self.llm.llm_chat(
                        prompt=prompt,
                        system_prompt=OUTPUT_SYNTHESIS_PROMPT,
                        response_format="text",
                        temperature=0.7,
                    )
                    logger.debug("Applied memory-aware synthesis for summarization")
                    return personalized_summary
                except Exception:
                    logger.debug(
                        "Memory-aware synthesis failed for summarization; returning original summary",
                        exc_info=True
                    )
            return summary_text
        
        elif tool_name == "followup":
            email_body = tool_result.get("body", "")
            subject = tool_result.get("subject", "")
            
            if memory_insights:
                try:
                    prompt = f"""You are personalizing a follow-up email body to match the user's communication style and preferences.

Original Email Body:
{email_body}

User Context / Memory:
- Communication style: {memory_insights.get('communication_style', '')}
- Preferences: {memory_insights.get('preferences', '')}
- Recurring topics: {memory_insights.get('recurring_topics', '')}
- Open loops: {memory_insights.get('open_loops', '')}

Rephrase the email body to align with the user's style and preferences while preserving all factual content and calls-to-action.
Do not add new facts. Return only the rephrased body."""
                    personalized_body = self.llm.llm_chat(
                        prompt=prompt,
                        system_prompt=OUTPUT_SYNTHESIS_PROMPT,
                        response_format="text",
                        temperature=0.7,
                    )
                    logger.debug("Applied memory-aware synthesis for followup body")
                    return {"subject": subject, "body": personalized_body}
                except Exception:
                    logger.debug(
                        "Memory-aware synthesis failed for followup; returning original body",
                        exc_info=True
                    )
            return {"subject": subject, "body": email_body}
        
        else:
            return "I've processed your request. Here's the result."

