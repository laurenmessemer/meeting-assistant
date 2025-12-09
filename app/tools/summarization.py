"""Summarization tool for post-meeting analysis."""

from typing import Dict, Any, Optional, List
from app.llm.gemini_client import GeminiClient
from app.llm.prompts import SUMMARIZATION_TOOL_PROMPT
from app.tools.memory_processing import synthesize_memory, get_relevant_past_summaries
from app.tools.delta_processing import compute_summary_deltas, build_delta_section


class SummarizationTool:
    """Tool for summarizing meetings and extracting decisions/actions."""
    
    def __init__(self, llm_client: GeminiClient):
        self.llm = llm_client
    
    async def summarize_meeting(
        self,
        transcript: Optional[str] = None,
        meeting_title: Optional[str] = None,
        meeting_date: Optional[str] = None,
        recording_date: Optional[str] = None,
        attendees: Optional[str] = None,
        has_transcript: bool = True,
        past_context: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Summarize a meeting and extract decisions/actions.
        
        Args:
            transcript: Meeting transcript text (required if has_transcript=True)
            meeting_title: Meeting title
            meeting_date: Calendar event date for display
            recording_date: Zoom recording date for display
            attendees: Comma-separated list of attendee names
            has_transcript: Whether transcript is available (default: True)
            past_context: Optional list of past meeting memories for context
        
        Returns:
            Dictionary with summary, decisions, and metadata
        """
        # Validate input
        if has_transcript and not transcript:
            return {
                "error": "Transcript is required when has_transcript=True"
            }
        
        # Use defaults for missing metadata
        title = meeting_title or "Untitled Meeting"
        date_str = meeting_date or "Unknown date"
        recording_date_str = recording_date or "N/A"
        attendees_display = attendees or "Not specified"
        
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
        
        # Get previous summaries for delta comparison (after summary generation)
        previous_summaries = []
        if past_context:
            previous_summaries = get_relevant_past_summaries(past_context)
        
        # Build delta section from previous summaries (compare most recent two)
        # Note: We can't compare current summary yet (doesn't exist), so we skip delta injection in prompt
        # Deltas will be computed after summary generation if needed
        delta_context_section = ""
        
        # Generate structured summary using LLM
        if not has_transcript:
            # Generate summary without transcript - just calendar information
            prompt = f"""Create a meeting summary based on the available calendar information. Note that no Zoom recording is available for this meeting.
{memory_context_section}{delta_context_section}

Meeting Information:
- Title: {title}
- Calendar Event Date: {date_str}
- Attendees: {attendees_display}

IMPORTANT: There is no Zoom recording or transcript available for this meeting. Please create a summary with the following EXACT structure and formatting:

# Meeting Header
{title}

## Date from calendar:
{date_str}

## Participants:
{attendees_display}

## Overview:
[Provide a brief 2-3 sentence summary based on the meeting title and attendees. Since no transcript is available, focus on what can be inferred from the meeting title and who was scheduled to attend.]

## Recording Status:
⚠️ No Zoom recording is available for this meeting. This summary is based solely on the calendar event information (title, date, and participants).

## Outline:
[Since no transcript is available, you cannot provide details about what was discussed. Instead, write: "No transcript available - unable to provide meeting outline."]

## Conclusion:
[Since no transcript is available, you cannot provide details about decisions or next steps. Instead, write: "No transcript available - unable to provide meeting conclusions."]

Format your response using the EXACT section headers shown above (with # and ## markdown formatting). Be clear, concise, and well-organized."""
        else:
            # Generate summary with transcript
            prompt = f"""Analyze the following meeting transcript and create a comprehensive, well-structured summary.
{memory_context_section}{delta_context_section}

Meeting Information:
- Title: {title}
- Calendar Event Date: {date_str}
- Zoom Recording Date: {recording_date_str}
- Attendees: {attendees_display}

Meeting Transcript:
{transcript}

Please create a summary with the following EXACT structure and formatting:

# Meeting Header
{title}

## Date from calendar:
{date_str}

## Participants:
{attendees_display}

## Overview:
[Provide a brief 2-3 sentence summary of what the meeting was about, who attended, and the main purpose. Focus on the key objectives and outcomes.]

## Outline:
[Provide 2-3 sentences summarizing the major sections or topics discussed in the meeting. Write in complete sentences (not bullet points) that outline what was covered in each main section. Keep it succinct and focused on the key discussion areas.]

## Conclusion:
[Provide a summary of decisions made, next steps, and any important takeaways. Include any commitments, agreements, or follow-up requirements.]

Format your response using the EXACT section headers shown above (with # and ## markdown formatting). Be clear, concise, and well-organized."""
        
        summary_text = self.llm.llm_chat(
            prompt=prompt,
            system_prompt=SUMMARIZATION_TOOL_PROMPT,
            response_format="text",
            temperature=0.3,  # Lower temperature for more factual summaries
        )
        
        # Extract structured data (decisions only) using LLM - skip if no transcript
        decisions = []
        if has_transcript:
            extraction_prompt = f"""Based on the following meeting summary, extract:
1. All decisions made (who decided what)

Meeting Summary:
{summary_text}

Respond in JSON format:
{{
    "decisions": [
        {{"description": "...", "context": "..."}}
    ]
}}"""
            
            structured_data = self.llm.llm_chat(
                prompt=extraction_prompt,
                response_format="JSON",
                temperature=0.2,
            )
            
            # Extract decisions from structured data
            if isinstance(structured_data, dict):
                decisions = structured_data.get("decisions", [])
        
        return {
            "summary": summary_text,
            "meeting_title": title,
            "meeting_date": date_str,
            "recording_date": recording_date_str,
            "attendees": attendees_display,
            "decisions": decisions,
            "has_transcript": has_transcript
        }
