"""Delta processing module for comparing summaries and highlighting changes."""

import re
from typing import Dict, Any, Optional, List
from app.llm.gemini_client import GeminiClient


def normalize_summary_text(text: str) -> str:
    """
    Normalize summary text for comparison.
    
    Args:
        text: Summary text to normalize
    
    Returns:
        Normalized text (lowercase, stripped, bullets removed, extra spacing removed)
    """
    if not text:
        return ""
    
    # Lowercase
    normalized = text.lower()
    
    # Strip whitespace
    normalized = normalized.strip()
    
    # Remove markdown headers (# and ##)
    normalized = re.sub(r'^#+\s*', '', normalized, flags=re.MULTILINE)
    
    # Remove bullets and list markers
    normalized = re.sub(r'^[\s]*[-•*]\s*', '', normalized, flags=re.MULTILINE)
    normalized = re.sub(r'^\d+\.\s*', '', normalized, flags=re.MULTILINE)
    
    # Remove extra whitespace (multiple spaces, tabs, newlines)
    normalized = re.sub(r'\s+', ' ', normalized)
    
    # Remove extra spacing around punctuation
    normalized = re.sub(r'\s*([.,;:!?])\s*', r'\1 ', normalized)
    
    # Final strip
    normalized = normalized.strip()
    
    return normalized


async def compute_summary_deltas(
    current_summary: str,
    previous_summaries: List[str],
    llm_client: GeminiClient
) -> Dict[str, List[str]]:
    """
    Compare current summary against previous summaries to identify changes.
    
    Args:
        current_summary: Current meeting summary text
        previous_summaries: List of previous meeting summaries (most recent first)
        llm_client: LLM client for intelligent delta computation
    
    Returns:
        Dictionary with delta categories:
        {
            "new_topics": List[str],
            "removed_topics": List[str],
            "repeated_topics": List[str],
            "new_decisions": List[str],
            "blockers_added": List[str],
            "blockers_resolved": List[str]
        }
        Returns empty dict on error or if no previous summaries.
    """
    if not current_summary or not previous_summaries:
        return {
            "new_topics": [],
            "removed_topics": [],
            "repeated_topics": [],
            "new_decisions": [],
            "blockers_added": [],
            "blockers_resolved": []
        }
    
    # Use the most recent previous summary for comparison
    previous_summary = previous_summaries[0] if previous_summaries else ""
    
    if not previous_summary:
        return {
            "new_topics": [],
            "removed_topics": [],
            "repeated_topics": [],
            "new_decisions": [],
            "blockers_added": [],
            "blockers_resolved": []
        }
    
    # Truncate summaries to prevent prompt bloat
    current_truncated = current_summary[:2000] + "..." if len(current_summary) > 2000 else current_summary
    previous_truncated = previous_summary[:2000] + "..." if len(previous_summary) > 2000 else previous_summary
    
    prompt = f"""Compare the following two meeting summaries and identify what changed.

Previous Meeting Summary:
{previous_truncated}

Current Meeting Summary:
{current_truncated}

Identify and extract:
1. New topics: Topics or themes introduced in the current meeting that were not in the previous meeting
2. Removed topics: Topics from the previous meeting that are no longer mentioned in the current meeting
3. Repeated topics: Topics that appear in both meetings (continuation of ongoing discussions)
4. New decisions: Decisions made in the current meeting that were not in the previous meeting
5. Blockers added: New blockers, obstacles, or issues mentioned in the current meeting
6. Blockers resolved: Blockers from the previous meeting that appear to be resolved in the current meeting

For each category, extract specific, concise items. If a category has no items, return an empty list.

Respond in JSON format:
{{
    "new_topics": ["topic 1", "topic 2"],
    "removed_topics": ["topic 1", "topic 2"],
    "repeated_topics": ["topic 1", "topic 2"],
    "new_decisions": ["decision 1", "decision 2"],
    "blockers_added": ["blocker 1", "blocker 2"],
    "blockers_resolved": ["blocker 1", "blocker 2"]
}}"""

    try:
        result = await llm_client.llm_chat(
            prompt=prompt,
            response_format="JSON",
            temperature=0.3,  # Lower temperature for more consistent extraction
        )
        
        # Ensure we have the expected structure
        if isinstance(result, dict):
            return {
                "new_topics": result.get("new_topics", []),
                "removed_topics": result.get("removed_topics", []),
                "repeated_topics": result.get("repeated_topics", []),
                "new_decisions": result.get("new_decisions", []),
                "blockers_added": result.get("blockers_added", []),
                "blockers_resolved": result.get("blockers_resolved", [])
            }
        else:
            # Fallback: return empty deltas
            return {
                "new_topics": [],
                "removed_topics": [],
                "repeated_topics": [],
                "new_decisions": [],
                "blockers_added": [],
                "blockers_resolved": []
            }
    except Exception:
        # On any error, return empty deltas (fail gracefully)
        return {
            "new_topics": [],
            "removed_topics": [],
            "repeated_topics": [],
            "new_decisions": [],
            "blockers_added": [],
            "blockers_resolved": []
        }


def build_delta_section(deltas: Dict[str, List[str]]) -> str:
    """
    Build formatted delta section from delta dictionary.
    
    Args:
        deltas: Dictionary with delta categories and lists of items
    
    Returns:
        Formatted delta section string, or empty string if no deltas
    """
    if not deltas:
        return ""
    
    # Check if any category has items
    has_deltas = any(
        deltas.get("new_topics", []) or
        deltas.get("removed_topics", []) or
        deltas.get("repeated_topics", []) or
        deltas.get("new_decisions", []) or
        deltas.get("blockers_added", []) or
        deltas.get("blockers_resolved", [])
    )
    
    if not has_deltas:
        return ""
    
    sections = []
    
    if deltas.get("new_topics"):
        sections.append(f"- New topics: {', '.join(deltas['new_topics'][:5])}")  # Limit to 5 items
    
    if deltas.get("removed_topics"):
        sections.append(f"- Removed topics: {', '.join(deltas['removed_topics'][:5])}")
    
    # Note: repeated_topics is computed but not shown in output (per user format requirements)
    
    if deltas.get("new_decisions"):
        sections.append(f"- Updated decisions: {', '.join(deltas['new_decisions'][:5])}")
    
    if deltas.get("blockers_added"):
        sections.append(f"- New blockers: {', '.join(deltas['blockers_added'][:5])}")
    
    if deltas.get("blockers_resolved"):
        sections.append(f"- Resolved blockers: {', '.join(deltas['blockers_resolved'][:5])}")
    
    if sections:
        delta_section = f"""
Changes Since Previous Meeting:
{chr(10).join(sections)}
"""
        # Enforce 800 character limit on delta section
        if len(delta_section) > 800:
            delta_section = delta_section[:800] + "..."
        return delta_section
    
    return ""

