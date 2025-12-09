"""Follow-up email generation tool."""

from typing import Dict, Any, Optional
from app.llm.gemini_client import GeminiClient
from app.llm.prompts import SUMMARIZATION_TOOL_PROMPT


class FollowUpTool:
    """Tool for generating follow-up emails."""
    
    def __init__(self, llm_client: GeminiClient):
        self.llm = llm_client
    
    async def generate_followup(
        self,
        meeting_summary: Optional[str] = None,
        transcript: Optional[str] = None,
        meeting_title: Optional[str] = None,
        client_name: Optional[str] = None,
        client_email: Optional[str] = None,
        action_items: Optional[list] = None,
        decisions: Optional[list] = None
    ) -> Dict[str, Any]:
        """
        Generate a follow-up email.
        
        Args:
            meeting_summary: Summary of the meeting
            transcript: Full meeting transcript (optional, for more context)
            meeting_title: Meeting title
            client_name: Client name
            client_email: Client email address
            action_items: List of action items from the meeting
            decisions: List of decisions made in the meeting
        
        Returns:
            Dictionary with email subject and body
        """
        # Build context for email generation
        context_parts = []
        
        if meeting_title:
            context_parts.append(f"Meeting: {meeting_title}")
        if client_name:
            context_parts.append(f"Client: {client_name}")
        if meeting_summary:
            context_parts.append(f"\nMeeting Summary:\n{meeting_summary}")
        if transcript:
            context_parts.append(f"\nFull Transcript:\n{transcript}")
        if action_items:
            action_items_text = "\n".join([f"- {item}" for item in action_items])
            context_parts.append(f"\nAction Items:\n{action_items_text}")
        if decisions:
            decisions_text = "\n".join([f"- {decision}" for decision in decisions])
            context_parts.append(f"\nDecisions:\n{decisions_text}")
        
        prompt = f"""Generate a professional follow-up email based on the meeting information below.

{chr(10).join(context_parts) if context_parts else "No meeting information provided."}

Please create a follow-up email that:
1. Thanks the client for their time
2. Summarizes key points discussed
3. Lists action items and next steps
4. Confirms any decisions made
5. Sets expectations for follow-up

The email should be professional, clear, and actionable. Respond in JSON format:
{{
    "subject": "Email subject line",
    "body": "Email body text"
}}"""
        
        email_data = self.llm.llm_chat(
            prompt=prompt,
            system_prompt=SUMMARIZATION_TOOL_PROMPT,
            response_format="JSON",
            temperature=0.7,
        )
        
        # Ensure we have the expected structure
        if isinstance(email_data, dict):
            subject = email_data.get("subject", "Follow-up: Meeting Summary")
            body = email_data.get("body", "Thank you for the meeting.")
        else:
            # Fallback if JSON parsing fails
            subject = f"Follow-up: {meeting_title or 'Meeting Summary'}"
            body = str(email_data) if email_data else "Thank you for the meeting."
        
        return {
            "subject": subject,
            "body": body,
            "client_name": client_name,
            "client_email": client_email
        }
