"""Main agent orchestrator."""

from typing import Dict, Any, Optional
from sqlalchemy.orm import Session

from app.llm.gemini_client import GeminiClient
from app.memory.repo import MemoryRepository
from app.tools.summarization import SummarizationTool
from app.tools.meeting_brief import MeetingBriefTool
from app.tools.followup import FollowUpTool
from app.integrations.google_calendar_client import GoogleCalendarClient

from app.orchestrator.intent_recognition import IntentRecognizer
from app.orchestrator.workflow_planning import WorkflowPlanner
from app.orchestrator.memory_retrieval import MemoryRetriever
from app.orchestrator.memory_writing import MemoryWriter
from app.orchestrator.tool_execution import ToolExecutor
from app.orchestrator.output_synthesis import OutputSynthesizer


class AgentOrchestrator:
    """Main orchestration pipeline for the agent."""
    
    def __init__(self, db: Session):
        self.db = db
        self.llm = GeminiClient()
        self.memory = MemoryRepository(db)
        # Initialize tools (calendar will be passed lazily when needed)
        self.summarization_tool = SummarizationTool(self.llm, self.memory, self.db, None)
        self.meeting_brief_tool = MeetingBriefTool(self.llm, self.memory)
        self.followup_tool = FollowUpTool(self.llm, self.memory)
        
        # Initialize component handlers
        self.intent_recognizer = IntentRecognizer(self.llm)
        self.workflow_planner = WorkflowPlanner(self.llm)
        self.memory_retriever = MemoryRetriever(self.memory)
        self.memory_writer = MemoryWriter(self.llm, self.memory)
        self.output_synthesizer = OutputSynthesizer(self.llm)
        self.tool_executor = ToolExecutor(
            self.db,
            self.memory,
            self.summarization_tool,
            self.meeting_brief_tool,
            self.followup_tool,
            self._get_calendar
        )
        
        # Don't initialize calendar client here - do it lazily when needed
        self._calendar = None
        self._calendar_error = None
    
    def _get_calendar(self):
        """Get calendar client, initializing it if needed."""
        if self._calendar is None and self._calendar_error is None:
            try:
                self._calendar = GoogleCalendarClient()
            except Exception as e:
                self._calendar_error = str(e)
                self._calendar = None
        return self._calendar
    
    async def process_message(
        self,
        message: str,
        user_id: Optional[int] = None,
        client_id: Optional[int] = None,
        selected_meeting_id: Optional[int] = None,
        selected_calendar_event_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Process a user message through the full orchestration pipeline.
        
        Args:
            message: User's message
            user_id: Optional user ID
            client_id: Optional client ID
            selected_meeting_id: Optional meeting ID selected from UI
            selected_calendar_event_id: Optional calendar event ID selected from UI
        
        Returns:
            Dictionary with response and metadata
        """
        # Step 1: Intent Recognition
        intent_data = await self.intent_recognizer.recognize(message)
        intent = intent_data.get("intent", "general")
        extracted_info = intent_data.get("extracted_info", {})
        
        # Step 2: Workflow Planning
        workflow = await self.workflow_planner.plan(intent, message, user_id, client_id)
        
        # Step 3: Memory Retrieval
        context = await self.memory_retriever.retrieve(user_id, client_id, intent, extracted_info)
        
        # Step 4: Tool Execution
        tool_output = await self.tool_executor.execute(
            intent,
            message,
            context,
            user_id,
            client_id,
            extracted_info,
            selected_meeting_id=selected_meeting_id,
            selected_calendar_event_id=selected_calendar_event_id
        )
        
        # Step 5: Output Synthesis
        response = await self.output_synthesizer.synthesize(
            message,
            intent,
            tool_output,
            context
        )
        
        # Step 6: Memory Writing
        await self.memory_writer.write(user_id, client_id, message, response, tool_output)
        
        # Check if tool output has meeting options (for selection)
        meeting_options = None
        if tool_output and tool_output.get("requires_selection") and tool_output.get("meeting_options"):
            # Convert meeting options to dict format for JSON serialization
            options_list = tool_output.get("meeting_options", [])
            meeting_options = []
            for opt in options_list:
                if hasattr(opt, 'dict'):  # Pydantic model
                    meeting_options.append(opt.dict())
                elif hasattr(opt, '__dict__'):  # Object with __dict__
                    meeting_options.append({
                        "id": getattr(opt, 'id', None),
                        "title": getattr(opt, 'title', None),
                        "date": getattr(opt, 'date', None),
                        "calendar_event_id": getattr(opt, 'calendar_event_id', None),
                        "meeting_id": getattr(opt, 'meeting_id', None),
                        "client_name": getattr(opt, 'client_name', None)
                    })
                else:  # Already a dict
                    meeting_options.append(opt)
        
        return {
            "response": response,
            "tool_used": tool_output.get("tool_name") if tool_output else None,
            "meeting_options": meeting_options,
            "metadata": {
                "intent": intent,
                "confidence": intent_data.get("confidence", 0.0),
                "workflow": workflow,
            }
        }
