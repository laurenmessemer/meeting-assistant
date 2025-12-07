"""Follow-up email generation tool."""

from typing import Dict, Any, Optional
from app.llm.gemini_client import GeminiClient
from app.llm.prompts import FOLLOWUP_TOOL_PROMPT
from app.memory.repo import MemoryRepository
from app.integrations.gmail_client import GmailClient


class FollowUpTool:
    """Tool for generating follow-up emails."""
    
    def __init__(
        self, 
        llm_client: GeminiClient, 
        memory_repo: MemoryRepository
    ):
        self.llm = llm_client
        self.memory = memory_repo
        self.gmail = GmailClient()
    
    def generate_followup_email(
        self,
        meeting_id: Optional[int] = None,
        client_id: Optional[int] = None,
        user_id: Optional[int] = None,
        additional_context: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate a follow-up email after a meeting.
        
        Args:
            meeting_id: Database meeting ID
            client_id: Client ID
            user_id: User ID
            additional_context: Additional context for the email
        
        Returns:
            Dictionary with email content
        """
        # Gather context
        context_parts = []
        
        # Get meeting summary if available
        if meeting_id:
            meeting = self.memory.get_meeting_by_id(meeting_id)
            if meeting:
                context_parts.append(f"Meeting: {meeting.title}")
                context_parts.append(f"Date: {meeting.scheduled_time}")
                if meeting.summary:
                    context_parts.append(f"\nMeeting Summary:\n{meeting.summary}")
                
                # Get decisions and actions from this meeting
                if meeting.client_id:
                    decisions = self.memory.get_decisions_by_client(meeting.client_id, limit=10)
                    meeting_decisions = [d for d in decisions if d.meeting_id == meeting_id]
                    if meeting_decisions:
                        context_parts.append("\nDecisions Made:")
                        for d in meeting_decisions:
                            context_parts.append(f"- {d.description}")
                    
                    actions = self.memory.get_actions_by_client(meeting.client_id)
                    meeting_actions = [a for a in actions if a.meeting_id == meeting_id]
                    if meeting_actions:
                        context_parts.append("\nAction Items:")
                        for a in meeting_actions:
                            assignee_text = f" ({a.assignee})" if a.assignee else ""
                            due_text = f" by {a.due_date}" if a.due_date else ""
                            context_parts.append(f"- {a.description}{assignee_text}{due_text}")
        
        # Get client context
        if client_id:
            client = self.memory.get_client_by_id(client_id)
            if client:
                context_parts.append(f"\nClient: {client.name}")
                if client.email:
                    context_parts.append(f"Email: {client.email}")
                
                # Get email tone samples
                if client.email:
                    try:
                        tone_samples = self.gmail.get_email_tone_samples(client.email, max_samples=3)
                        if tone_samples:
                            context_parts.append("\nPast Email Tone Samples:")
                            for i, sample in enumerate(tone_samples[:2], 1):
                                # Use first 200 chars of each sample
                                sample_text = sample[:200] + "..." if len(sample) > 200 else sample
                                context_parts.append(f"\nSample {i}:\n{sample_text}")
                    except Exception:
                        pass
        
        # Add any additional context
        if additional_context:
            context_parts.append(f"\nAdditional Context:\n{additional_context}")
        
        context_text = "\n".join(context_parts)
        
        if not context_text.strip():
            raise ValueError("Insufficient context to generate follow-up email")
        
        # Generate email using LLM
        prompt = f"""Context:
{context_text}

Generate a professional follow-up email based on the above information."""
        
        email_text = self.llm.generate(
            prompt,
            system_prompt=FOLLOWUP_TOOL_PROMPT,
            temperature=0.8,  # Slightly higher for more natural language
        )
        
        # Extract subject line if present
        subject = None
        body = email_text
        
        if "Subject:" in email_text:
            parts = email_text.split("Subject:", 1)
            if len(parts) == 2:
                subject_line = parts[1].split("\n", 1)[0].strip()
                body = parts[1].split("\n", 1)[1] if "\n" in parts[1] else parts[1]
                subject = subject_line
        elif email_text.startswith("Subject:"):
            lines = email_text.split("\n", 2)
            if len(lines) >= 2:
                subject = lines[0].replace("Subject:", "").strip()
                body = lines[2] if len(lines) > 2 else lines[1]
        
        return {
            "subject": subject or "Follow-up: Meeting Discussion",
            "body": body.strip(),
            "full_email": email_text,
            "client_id": client_id,
            "meeting_id": meeting_id,
        }

