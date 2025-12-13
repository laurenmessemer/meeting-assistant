"""Delta processing service - centralizes logic for computing summary deltas."""

from typing import Dict, Any, Optional, List
from app.llm.gemini_client import GeminiClient
from app.tools.memory_processing import get_relevant_past_summaries
from app.tools.delta_processing import compute_summary_deltas, build_delta_section


async def compute_delta_context(
    current_summary: Optional[str],
    past_context: List[Dict[str, Any]],
    llm: GeminiClient
) -> str:
    """
    Compute delta context section by comparing current summary with past summaries.
    
    Args:
        current_summary: Current meeting summary text (may be None)
        past_context: List of memory entry dicts with 'value' and 'extra_data' keys
        llm: LLM client for delta computation
    
    Returns:
        Formatted delta context section string, or empty string if no deltas or no summary.
    """
    # If no current summary, return empty string
    if not current_summary:
        return ""
    
    # Extract past summaries from memory
    previous_summaries = get_relevant_past_summaries(past_context)
    
    # If no previous summaries, return empty string
    if not previous_summaries:
        return ""
    
    # Compute deltas using existing logic
    try:
        deltas = await compute_summary_deltas(
            current_summary=current_summary,
            previous_summaries=previous_summaries,
            llm_client=llm
        )
        
        # Build formatted delta section
        delta_context_section = build_delta_section(deltas)
        
        return delta_context_section
    except Exception:
        # Fail gracefully - return empty string on any error
        return ""

