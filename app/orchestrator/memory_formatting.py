"""Memory formatting module for formatting memory insights into prompt context."""

from typing import Dict, Any


def format_memory_context(memory_insights: Dict[str, str]) -> str:
    """
    Format memory insights into a context section for prompts.
    
    Args:
        memory_insights: Dictionary with structured insights:
            {
                "communication_style": str,
                "client_history": str,
                "recurring_topics": str,
                "open_loops": str,
                "preferences": str
            }
    
    Returns:
        Formatted memory context section string, or empty string if all values are empty.
        Truncated to 1200 characters if longer.
    """
    if not memory_insights:
        return ""
    
    # Check if all values are empty
    if not any(memory_insights.values()):
        return ""
    
    # Format memory context section
    memory_context_section = f"""
User Context / Memory:
- Communication style: {memory_insights.get('communication_style', '')}
- Preferences: {memory_insights.get('preferences', '')}
- Recurring topics: {memory_insights.get('recurring_topics', '')}
- Open loops: {memory_insights.get('open_loops', '')}
"""
    
    # Enforce 1200 character limit
    if len(memory_context_section) > 1200:
        memory_context_section = memory_context_section[:1200] + "..."
    
    return memory_context_section

