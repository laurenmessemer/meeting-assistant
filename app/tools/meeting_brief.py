"""Meeting brief tool for pre-meeting preparation."""

from typing import Dict, Any, Optional, List
from datetime import datetime
from app.llm.gemini_client import GeminiClient
from app.llm.prompts import MEETING_BRIEF_TOOL_PROMPT
from app.memory.repo import MemoryRepository
from app.memory.schemas import ClientCreate
from app.integrations.hubspot_client import HubSpotClient
from app.integrations.google_calendar_client import GoogleCalendarClient
from app.integrations.google_drive_client import GoogleDriveClient


class MeetingBriefTool:
    """Tool for generating meeting briefs before meetings."""
    
    def __init__(
        self, 
        llm_client: GeminiClient, 
        memory_repo: MemoryRepository
    ):
        self.llm = llm_client
        self.memory = memory_repo
        self.hubspot = HubSpotClient()
        self.calendar = GoogleCalendarClient()
        self.drive = GoogleDriveClient()
    
    async def generate_brief(
        self,
        meeting_id: Optional[int] = None,
        calendar_event_id: Optional[str] = None,
        client_id: Optional[int] = None,
        user_id: Optional[int] = None,
        client_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate a comprehensive meeting brief.
        
        Args:
            meeting_id: Database meeting ID (if meeting already exists)
            calendar_event_id: Google Calendar event ID
            client_id: Client ID (if known)
            user_id: User ID
        
        Returns:
            Dictionary with meeting brief content
        """
        # Get meeting information
        meeting_info = None
        calendar_error = None
        
        try:
            if calendar_event_id:
                calendar_event = self.calendar.get_event_by_id(calendar_event_id)
                if calendar_event:
                    meeting_info = self.calendar.extract_meeting_info(calendar_event)
            
            # If client name is provided, search for meetings matching that client
            if not meeting_info and client_name:
                try:
                    # First, try exact match
                    matching_events = self.calendar.search_events_by_keyword(client_name, max_results=10)
                    if matching_events:
                        # Use the first matching event (should be the soonest)
                        meeting_info = self.calendar.extract_meeting_info(matching_events[0])
                    else:
                        # Try partial match - search for each word in client name
                        client_words = client_name.split()
                        for word in client_words:
                            if len(word) > 2:  # Skip very short words
                                matching_events = self.calendar.search_events_by_keyword(word, max_results=5)
                                if matching_events:
                                    # Check if any match contains the full client name
                                    for event in matching_events:
                                        event_title = event.get('summary', '').lower()
                                        if client_name.lower() in event_title:
                                            meeting_info = self.calendar.extract_meeting_info(event)
                                            break
                                    if meeting_info:
                                        break
                except Exception as e:
                    calendar_error = str(e)
                    pass
            
            # If no specific event or client name match, try to get upcoming meetings
            if not meeting_info:
                try:
                    upcoming_events = self.calendar.get_upcoming_events(max_results=10)
                    if upcoming_events:
                        # If client_name was specified but no match found, raise error
                        if client_name:
                            raise ValueError(
                                f"No meetings found matching '{client_name}'. "
                                f"Found {len(upcoming_events)} upcoming meetings, but none match the specified client."
                            )
                        # Otherwise, use the first upcoming event
                        meeting_info = self.calendar.extract_meeting_info(upcoming_events[0])
                except ValueError:
                    # Re-raise ValueError (client name not found)
                    raise
                except Exception as e:
                    calendar_error = str(e)
                    # If calendar access fails, we'll handle it below
                    pass
        except ValueError:
            # Re-raise ValueError (client name not found)
            raise
        except Exception as e:
            calendar_error = str(e)
            # Calendar might not be authenticated yet
        
        if not meeting_info:
            error_msg = "No meeting information available."
            if client_name:
                error_msg = f"No meeting found matching '{client_name}' in your Google Calendar."
                error_msg += " Please check that:"
                error_msg += f"\n- The meeting with {client_name} exists in your calendar"
                error_msg += f"\n- The client name '{client_name}' appears in the meeting title, description, or location"
                error_msg += "\n- The meeting is scheduled within the next 30 days"
            elif calendar_error:
                if "credentials" in calendar_error.lower() or "authentication" in calendar_error.lower():
                    error_msg += " Google Calendar authentication required. Please authenticate when prompted."
                else:
                    error_msg += f" Calendar error: {calendar_error}"
            else:
                error_msg += " Please specify a meeting date/time or ensure your Google Calendar has upcoming events."
            raise ValueError(error_msg)
        
        # Identify client
        client = None
        client_context = {}
        
        if client_id:
            client = self.memory.get_client_by_id(client_id)
        elif client_name:
            # Try to find client by name in database first
            if user_id:
                all_clients = self.memory.get_clients_by_user(user_id)
                for c in all_clients:
                    if client_name.lower() in c.name.lower() or (c.company and client_name.lower() in c.company.lower()):
                        client = c
                        break
            
            # If not found in database, try to find via HubSpot
            if not client and meeting_info:
            # Try to identify client from attendees
            attendees = meeting_info.get("attendees", [])
            for attendee in attendees:
                email = attendee.get("email")
                if email:
                    # Search HubSpot for contact
                    try:
                        hubspot_contact = await self.hubspot.get_contact_by_email(email)
                        if hubspot_contact:
                            hubspot_id = hubspot_contact.get("id")
                            # Get or create client in database
                            client = self.memory.get_client_by_hubspot_id(hubspot_id)
                            if not client and user_id:
                                client = self.memory.create_client(
                                    ClientCreate(
                                        user_id=user_id,
                                        hubspot_id=hubspot_id,
                                        name=hubspot_contact.get("properties", {}).get("firstname", "") + " " + 
                                             hubspot_contact.get("properties", {}).get("lastname", ""),
                                        email=email,
                                        company=hubspot_contact.get("properties", {}).get("company"),
                                        metadata=hubspot_contact.get("properties", {}),
                                    )
                                )
                            break
                    except Exception:
                        continue
        
        # Gather context
        context_parts = []
        
        # Meeting details
        context_parts.append(f"Meeting: {meeting_info.get('title', 'Untitled')}")
        context_parts.append(f"Scheduled: {meeting_info.get('start_time', 'Unknown')}")
        context_parts.append(f"Attendees: {', '.join([a.get('email', '') for a in meeting_info.get('attendees', [])])}")
        if meeting_info.get('description'):
            context_parts.append(f"Description: {meeting_info.get('description')}")
        
        # Client context
        if client:
            client_context = self.memory.get_client_context(client.id)
            context_parts.append(f"\nClient: {client.name} ({client.company or 'N/A'})")
            
            # Add recent meetings
            if client_context.get("recent_meetings"):
                context_parts.append("\nRecent Meetings:")
                for m in client_context["recent_meetings"][:3]:
                    context_parts.append(f"- {m['title']} ({m['scheduled_time']})")
            
            # Add pending actions
            if client_context.get("actions"):
                pending = [a for a in client_context["actions"] if a["status"] == "pending"]
                if pending:
                    context_parts.append("\nPending Actions:")
                    for a in pending[:5]:
                        context_parts.append(f"- {a['description']}")
            
            # Add recent decisions
            if client_context.get("decisions"):
                context_parts.append("\nRecent Decisions:")
                for d in client_context["decisions"][:5]:
                    context_parts.append(f"- {d['description']}")
        
        # Search for relevant documents
        if client:
            client_name = client.name or client.company or ""
            if client_name:
                try:
                    docs = self.drive.search_files_by_client_name(client_name, max_results=5)
                    if docs:
                        context_parts.append("\nRelevant Documents:")
                        for doc in docs:
                            context_parts.append(f"- {doc.get('name')} ({doc.get('webViewLink')})")
                except Exception:
                    pass
        
        # Get HubSpot deals if client exists
        if client and client.hubspot_id:
            try:
                deals = await self.hubspot.get_deals_for_contact(client.hubspot_id)
                if deals:
                    context_parts.append("\nActive Deals:")
                    for deal in deals[:3]:
                        deal_props = deal.get("properties", {})
                        context_parts.append(
                            f"- {deal_props.get('dealname', 'N/A')} "
                            f"({deal_props.get('dealstage', 'N/A')}) - "
                            f"${deal_props.get('amount', '0')}"
                        )
            except Exception:
                pass
        
        context_text = "\n".join(context_parts)
        
        # Generate brief using LLM
        prompt = f"""Context Information:
{context_text}

Generate a comprehensive meeting brief based on the above information."""
        
        brief_text = self.llm.generate(
            prompt,
            system_prompt=MEETING_BRIEF_TOOL_PROMPT,
            temperature=0.7,
        )
        
        return {
            "brief": brief_text,
            "meeting_info": meeting_info,
            "client_id": client.id if client else None,
            "context_used": {
                "has_client": client is not None,
                "has_recent_meetings": bool(client_context.get("recent_meetings")),
                "has_pending_actions": bool([a for a in client_context.get("actions", []) if a["status"] == "pending"]),
                "has_documents": bool(context_parts),
            }
        }

