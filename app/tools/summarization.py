"""Summarization tool for post-meeting analysis."""

from typing import Dict, Any, Optional
from app.llm.gemini_client import GeminiClient
from app.llm.prompts import SUMMARIZATION_TOOL_PROMPT
from app.memory.repo import MemoryRepository
from app.memory.schemas import DecisionCreate, ActionCreate, MeetingUpdate
from app.integrations.zoom_client import ZoomClient


class SummarizationTool:
    """Tool for summarizing meetings and extracting decisions/actions."""
    
    def __init__(self, llm_client: GeminiClient, memory_repo: MemoryRepository):
        self.llm = llm_client
        self.memory = memory_repo
    
    async def summarize_meeting(
        self,
        meeting_id: int,
        transcript: Optional[str] = None,
        zoom_meeting_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Summarize a meeting and extract decisions/actions.
        
        Args:
            meeting_id: Database meeting ID
            transcript: Optional transcript text
            zoom_meeting_id: Optional Zoom meeting ID to fetch transcript
        
        Returns:
            Dictionary with summary, decisions, and actions
        """
        # Get meeting from database
        meeting = self.memory.get_meeting_by_id(meeting_id)
        if not meeting:
            raise ValueError(f"Meeting {meeting_id} not found")
        
        # Fetch transcript if not provided
        if not transcript and zoom_meeting_id:
            zoom_client = ZoomClient()
            recordings = await zoom_client.get_meeting_recordings(zoom_meeting_id)
            if recordings:
                # Try to get transcript from first recording
                recording_id = recordings[0].get("id")
                if recording_id:
                    transcript = await zoom_client.get_meeting_transcript(
                        zoom_meeting_id, 
                        recording_id
                    )
        
        if not transcript:
            raise ValueError("No transcript available for summarization")
        
        # Generate summary using LLM
        prompt = f"""Meeting Transcript:
{transcript}

Please provide a comprehensive summary following the format specified in the system prompt."""
        
        summary_text = self.llm.generate(
            prompt,
            system_prompt=SUMMARIZATION_TOOL_PROMPT,
            temperature=0.3,  # Lower temperature for more factual summaries
        )
        
        # Extract structured data (decisions and actions) using LLM
        extraction_prompt = f"""Based on the following meeting summary, extract:
1. All decisions made (who decided what)
2. All action items (who needs to do what by when)

Meeting Summary:
{summary_text}

Respond in JSON format:
{{
    "decisions": [
        {{"description": "...", "context": "..."}}
    ],
    "actions": [
        {{"description": "...", "assignee": "...", "due_date": "YYYY-MM-DD or null"}}
    ]
}}"""
        
        structured_data = self.llm.generate_structured(
            extraction_prompt,
            response_format="JSON",
            temperature=0.2,
        )
        
        # Update meeting with summary
        self.memory.update_meeting(
            meeting_id,
            MeetingUpdate(summary=summary_text, transcript=transcript)
        )
        
        # Store decisions and actions
        decisions = []
        actions = []
        
        if meeting.client_id:
            for decision_data in structured_data.get("decisions", []):
                decision = self.memory.create_decision(
                    DecisionCreate(
                        meeting_id=meeting_id,
                        client_id=meeting.client_id,
                        description=decision_data.get("description", ""),
                        context=decision_data.get("context"),
                    )
                )
                decisions.append(decision)
            
            for action_data in structured_data.get("actions", []):
                due_date_str = action_data.get("due_date")
                due_date = None
                if due_date_str:
                    from datetime import datetime
                    try:
                        due_date = datetime.fromisoformat(due_date_str)
                    except ValueError:
                        pass
                
                action = self.memory.create_action(
                    ActionCreate(
                        meeting_id=meeting_id,
                        client_id=meeting.client_id,
                        description=action_data.get("description", ""),
                        assignee=action_data.get("assignee"),
                        due_date=due_date,
                    )
                )
                actions.append(action)
        
        return {
            "summary": summary_text,
            "decisions": [
                {
                    "id": d.id,
                    "description": d.description,
                    "context": d.context,
                }
                for d in decisions
            ],
            "actions": [
                {
                    "id": a.id,
                    "description": a.description,
                    "assignee": a.assignee,
                    "due_date": a.due_date.isoformat() if a.due_date else None,
                    "status": a.status,
                }
                for a in actions
            ],
        }

