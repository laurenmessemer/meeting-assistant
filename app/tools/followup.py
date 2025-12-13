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
        meeting_date: Optional[str] = None,
        client_name: Optional[str] = None,
        client_email: Optional[str] = None,
        attendees: Optional[str] = None,
        action_items: Optional[list] = None,
        decisions: Optional[list] = None,
        memory_context_section: Optional[str] = "",
        delta_context_section: Optional[str] = "",
        meeting_id: Optional[int] = None,
        calendar_event_id: Optional[str] = None,
        meeting_source: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate a follow-up email.
        
        Args:
            meeting_summary: Summary of the meeting
            transcript: Full meeting transcript (optional, for more context)
            meeting_title: Meeting title
            meeting_date: Formatted meeting date string
            client_name: Client name
            client_email: Client email address
            attendees: Attendees list as formatted string
            action_items: List of action items from the meeting
            decisions: List of decisions made in the meeting (can be dicts with description/context)
            memory_context_section: Optional pre-formatted memory context section
            delta_context_section: Optional pre-formatted delta context section
            meeting_id: Optional meeting ID for diagnostic logging
            calendar_event_id: Optional calendar event ID for diagnostic logging
            meeting_source: Optional source indicator for diagnostic logging
        
        Returns:
            Dictionary with email subject and body
        """
        # DIAGNOSTIC: Log what meeting actually gets passed
        print(f"\n[FOLLOWUP DEBUG] generate_followup called")
        print(f"[FOLLOWUP DEBUG] meeting_source={meeting_source}")
        print(f"[FOLLOWUP DEBUG] meeting_id={meeting_id}")
        print(f"[FOLLOWUP DEBUG] calendar_event_id={calendar_event_id}")
        print(f"[FOLLOWUP DEBUG] meeting_title='{meeting_title}'")
        print(f"[FOLLOWUP DEBUG] meeting_date='{meeting_date}'")
        print(f"[FOLLOWUP DEBUG] client_name='{client_name}'")
        print(f"[FOLLOWUP DEBUG] client_email='{client_email}'")
        print(f"[FOLLOWUP DEBUG] has_meeting_summary={meeting_summary is not None} (length={len(meeting_summary) if meeting_summary else 0})")
        print(f"[FOLLOWUP DEBUG] has_transcript={transcript is not None} (length={len(transcript) if transcript else 0})")
        print(f"[FOLLOWUP DEBUG] decisions_count={len(decisions) if decisions else 0}")
        
        # Build structured context for email generation
        meeting_info_parts = []
        
        if meeting_title:
            meeting_info_parts.append(f"- Title: {meeting_title}")
        if meeting_date:
            meeting_info_parts.append(f"- Date: {meeting_date}")
        if client_name:
            meeting_info_parts.append(f"- Client: {client_name}")
        if attendees:
            meeting_info_parts.append(f"- Attendees: {attendees}")
        
        # Format decisions if provided
        decisions_text = ""
        if decisions:
            if isinstance(decisions[0], dict):
                # Decisions are dicts with description/context
                decisions_list = []
                for d in decisions:
                    desc = d.get("description", "")
                    context = d.get("context", "")
                    if context:
                        decisions_list.append(f"• {desc} (Context: {context})")
                    else:
                        decisions_list.append(f"• {desc}")
                decisions_text = "\n".join(decisions_list)
            else:
                # Decisions are simple strings
                decisions_text = "\n".join([f"• {d}" for d in decisions])
        
        # Format action items if provided
        action_items_text = ""
        if action_items:
            if isinstance(action_items[0], dict):
                # Action items are dicts
                items_list = []
                for item in action_items:
                    if isinstance(item, dict):
                        desc = item.get("description", item.get("item", ""))
                        owner = item.get("owner", item.get("assigned_to", ""))
                        if owner:
                            items_list.append(f"• {desc} (Assigned to: {owner})")
                        else:
                            items_list.append(f"• {desc}")
                    else:
                        items_list.append(f"• {item}")
                action_items_text = "\n".join(items_list)
            else:
                # Action items are simple strings
                action_items_text = "\n".join([f"• {item}" for item in action_items])
        
        # Build comprehensive prompt similar to summarization style
        prompt = f"""Generate a professional follow-up email based on the meeting information below.
{memory_context_section if memory_context_section else ""}{delta_context_section if delta_context_section else ""}

Meeting Information:
{chr(10).join(meeting_info_parts) if meeting_info_parts else "No meeting information provided."}

Meeting Summary:
{meeting_summary if meeting_summary else "No summary available."}

{f"Full Transcript (for additional context):{chr(10)}{transcript}" if transcript else ""}

{f"Decisions Made:{chr(10)}{decisions_text}" if decisions_text else ""}

{f"Action Items & Next Steps:{chr(10)}{action_items_text}" if action_items_text else ""}

Please create a follow-up email that:
1. Opens with a warm thank you for the client's time
2. Briefly summarizes the key points discussed (2-3 sentences)
3. Clearly lists action items and next steps, indicating who is responsible for each
4. Confirms any decisions that were made
5. Sets clear expectations for follow-up communication or next meeting

The email should be:
- Professional and warm in tone
- Clear and concise
- Actionable with specific next steps
- Appropriate for the client relationship

Respond in JSON format:
{{
    "subject": "Email subject line",
    "body": "Email body text (use proper email formatting with paragraphs)"
}}"""
        
        email_data = self.llm.llm_chat(
            prompt=prompt,
            system_prompt=SUMMARIZATION_TOOL_PROMPT,
            response_format="JSON",
            temperature=0.7,
        )
        
        # Ensure we have the expected structure
        if isinstance(email_data, dict):
            subject = email_data.get("subject", f"Follow-up: {meeting_title or 'Meeting Summary'}")
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
