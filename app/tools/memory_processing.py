"""Memory processing module for synthesizing insights from past context."""

from typing import Dict, Any, Optional, List
from app.llm.gemini_client import GeminiClient


def sanitize_memory_value(value: Optional[str]) -> str:
    """
    Sanitize a single memory value.
    
    Args:
        value: Memory value string (may be None)
    
    Returns:
        Sanitized string (truncated to 500 chars, stripped whitespace)
    """
    if not value:
        return ""
    
    # Strip whitespace
    sanitized = value.strip()
    
    # Truncate to 500 characters
    if len(sanitized) > 500:
        sanitized = sanitized[:500] + "..."
    
    return sanitized


def sanitize_past_context(past_context: Optional[List[Dict[str, Any]]]) -> List[str]:
    """
    Sanitize past context list.
    
    Args:
        past_context: List of memory entry dicts with 'value' key
    
    Returns:
        List of sanitized memory value strings
    """
    if not past_context:
        return []
    
    sanitized = []
    for mem in past_context:
        if isinstance(mem, dict):
            value = mem.get("value", "")
            sanitized_value = sanitize_memory_value(value)
            if sanitized_value:  # Only add non-empty values
                sanitized.append(sanitized_value)
    
    return sanitized


async def synthesize_memory(
    past_context: Optional[List[Dict[str, Any]]],
    llm_client: GeminiClient
) -> Dict[str, str]:
    """
    Synthesize insights from past context using LLM.
    
    Args:
        past_context: List of memory entry dicts with 'value' key
        llm_client: LLM client for synthesis
    
    Returns:
        Dictionary with structured insights:
        {
            "communication_style": str,
            "client_history": str,
            "recurring_topics": str,
            "open_loops": str,
            "preferences": str
        }
        All fields are empty strings if no memory exists or synthesis fails.
    """
    # Sanitize past context
    sanitized_memories = sanitize_past_context(past_context)
    
    # If no memories, return empty insights
    if not sanitized_memories:
        return {
            "communication_style": "",
            "client_history": "",
            "recurring_topics": "",
            "open_loops": "",
            "preferences": ""
        }
    
    # Build context for LLM
    memories_text = "\n".join([f"- {mem}" for mem in sanitized_memories])
    
    prompt = f"""Analyze the following past meeting interactions and extract structured insights.

Past Meeting Context:
{memories_text}

Extract and synthesize the following insights:

1. Communication Style: How does the user typically communicate? What tone, formality level, and writing patterns do you observe?

2. Client History: What patterns emerge about this specific client's prior meetings? What topics, concerns, or themes recur?

3. Recurring Topics: What themes or subjects appear across multiple interactions? What topics are frequently discussed?

4. Open Loops: What commitments, TODOs, or action items were mentioned but may not have been completed? What follow-ups are pending?

5. Preferences: What preferences does the user have for summarization style, follow-up tone, or meeting brief format?

Respond in JSON format:
{{
    "communication_style": "Brief description of communication patterns",
    "client_history": "Patterns about this client's prior meetings",
    "recurring_topics": "Themes that appear across interactions",
    "open_loops": "Pending commitments or TODOs",
    "preferences": "User preferences for tone and format"
}}

If you cannot extract meaningful insights for any field, return an empty string for that field."""

    try:
        result = await llm_client.llm_chat(
            prompt=prompt,
            response_format="JSON",
            temperature=0.4,  # Lower temperature for more consistent extraction
        )
        
        # Ensure we have the expected structure
        if isinstance(result, dict):
            return {
                "communication_style": result.get("communication_style", ""),
                "client_history": result.get("client_history", ""),
                "recurring_topics": result.get("recurring_topics", ""),
                "open_loops": result.get("open_loops", ""),
                "preferences": result.get("preferences", "")
            }
        else:
            # Fallback: return empty insights
            return {
                "communication_style": "",
                "client_history": "",
                "recurring_topics": "",
                "open_loops": "",
                "preferences": ""
            }
    except Exception:
        # On any error, return empty insights (fail gracefully)
        return {
            "communication_style": "",
            "client_history": "",
            "recurring_topics": "",
            "open_loops": "",
            "preferences": ""
        }

