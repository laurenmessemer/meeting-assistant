"""Main agent orchestrator."""

from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from datetime import datetime

from app.llm.gemini_client import GeminiClient
from app.memory.repo import MemoryRepository
from app.tools.summarization import SummarizationTool
from app.tools.meeting_brief import MeetingBriefTool
from app.tools.followup import FollowUpTool

from app.orchestrator.intent_recognition import IntentRecognizer
from app.orchestrator.workflow_planning import WorkflowPlanner
from app.orchestrator.memory_retrieval import MemoryRetriever
from app.orchestrator.memory_synthesis_service import MemorySynthesisService
from app.orchestrator.memory_formatting import format_memory_context
from app.orchestrator.data_preparation import DataPreparator
from app.orchestrator.integration_data_fetching import IntegrationDataFetcher
from app.orchestrator.tool_execution import ToolExecutor
from app.orchestrator.output_synthesis import OutputSynthesizer
from app.orchestrator.memory_writing import MemoryWriter
from app.utils.logging_utils import StructuredLogger, generate_correlation_id


class AgentOrchestrator:
    """Main orchestration pipeline for the agent."""
    
    def __init__(self, db: Session):
        self.db = db
        self.llm = GeminiClient()
        self.memory = MemoryRepository(db)
        self.logger = StructuredLogger()
        
        # Initialize tools (now only need LLM client)
        self.summarization_tool = SummarizationTool(self.llm)
        self.meeting_brief_tool = MeetingBriefTool(self.llm)
        self.followup_tool = FollowUpTool(self.llm)
        
        # Initialize pipeline components
        self.intent_recognizer = IntentRecognizer(self.llm)
        self.workflow_planner = WorkflowPlanner(self.llm)
        self.memory_retriever = MemoryRetriever(self.memory)
        self.memory_synthesis_service = MemorySynthesisService()
        self.data_preparator = DataPreparator()
        self.integration_data_fetcher = IntegrationDataFetcher(self.db, self.memory)
        self.tool_executor = ToolExecutor(
            self.db,
            self.memory,
            self.summarization_tool,
            self.meeting_brief_tool,
            self.followup_tool,
            self.integration_data_fetcher
        )
        self.output_synthesizer = OutputSynthesizer(self.llm)
        self.memory_writer = MemoryWriter(self.llm, self.memory)
    
    async def process_message(
        self,
        message: str,
        user_id: Optional[int] = None,
        client_id: Optional[int] = None,
        selected_meeting_id: Optional[int] = None,
        selected_calendar_event_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        debug: bool = False
    ) -> Dict[str, Any]:
        """
        Process a user message through the full orchestration pipeline.
        
        Pipeline:
        1. Intent Recognition
        2. Planning
        3. Memory Retrieval
        4. Integration Data Fetching
        5. Tool Execution
        6. Output Synthesis
        7. Memory Write
        
        Args:
            message: User's message
            user_id: Optional user ID
            client_id: Optional client ID
            selected_meeting_id: Optional meeting ID selected from UI
            selected_calendar_event_id: Optional calendar event ID selected from UI
            correlation_id: Optional correlation ID for request tracking
            debug: If True, include intermediate outputs in response
        
        Returns:
            Dictionary with response and metadata
        """
        # Generate correlation ID if not provided
        if not correlation_id:
            correlation_id = generate_correlation_id()
        
        start_time = datetime.utcnow()
        intermediate_outputs = {} if debug else None
        
        self.logger.info(
            "Agent pipeline started",
            correlation_id=correlation_id,
            message_length=len(message),
            user_id=user_id,
            client_id=client_id
        )
        
        try:
            # Step 1: Intent Recognition
            step_start = datetime.utcnow()
            self.logger.debug(
                "Step 1: Intent recognition started",
                correlation_id=correlation_id,
                step="intent_recognition"
            )
            
            try:
                intent_data = await self.intent_recognizer.recognize(message)
                intent = intent_data.get("intent", "general")
                extracted_info = intent_data.get("extracted_info", {})
                step_duration = (datetime.utcnow() - step_start).total_seconds() * 1000
                
                self.logger.info(
                    "Step 1: Intent recognition completed",
                    correlation_id=correlation_id,
                    step="intent_recognition",
                    duration_ms=step_duration,
                    intent=intent,
                    confidence=intent_data.get("confidence", 0.0)
                )
                
                if debug:
                    intermediate_outputs["intent_data"] = intent_data
            except Exception as e:
                self.logger.error(
                    "Step 1: Intent recognition failed",
                    correlation_id=correlation_id,
                    step="intent_recognition",
                    error=str(e),
                    error_type=type(e).__name__
                )
                # Failure-safe: use general intent
                intent_data = {"intent": "general", "confidence": 0.5, "extracted_info": {}}
                intent = "general"
                extracted_info = {}
                if debug:
                    intermediate_outputs["intent_data"] = intent_data
                    intermediate_outputs["intent_error"] = str(e)
            
            # Step 2: Planning
            step_start = datetime.utcnow()
            self.logger.debug(
                "Step 2: Workflow planning started",
                correlation_id=correlation_id,
                step="workflow_planning"
            )
            
            try:
                workflow = await self.workflow_planner.plan(intent, message, user_id, client_id)
                step_duration = (datetime.utcnow() - step_start).total_seconds() * 1000
                
                self.logger.info(
                    "Step 2: Workflow planning completed",
                    correlation_id=correlation_id,
                    step="workflow_planning",
                    duration_ms=step_duration,
                    steps_count=len(workflow.get("steps", []))
                )
                
                if debug:
                    intermediate_outputs["workflow"] = workflow
            except Exception as e:
                self.logger.error(
                    "Step 2: Workflow planning failed",
                    correlation_id=correlation_id,
                    step="workflow_planning",
                    error=str(e),
                    error_type=type(e).__name__
                )
                # Failure-safe: use empty workflow
                workflow = {"steps": []}
                if debug:
                    intermediate_outputs["workflow"] = workflow
                    intermediate_outputs["workflow_error"] = str(e)
            
            # Step 3: Memory Retrieval
            step_start = datetime.utcnow()
            self.logger.debug(
                "Step 3: Memory retrieval started",
                correlation_id=correlation_id,
                step="memory_retrieval"
            )
            
            try:
                context = await self.memory_retriever.retrieve(user_id, client_id, intent, extracted_info)
                # Store original message in context for last meeting auto-resolution
                context["message"] = message
                
                # Synthesize memory insights once per request
                try:
                    user_memories = context.get("user_memories", [])
                    past_context = user_memories[:5] if user_memories else None
                    if past_context:
                        memory_insights = await self.memory_synthesis_service.synthesize(past_context, self.llm)
                        context["memory_insights"] = memory_insights
                    else:
                        # No memories available, set empty insights
                        context["memory_insights"] = {
                            "communication_style": "",
                            "client_history": "",
                            "recurring_topics": "",
                            "open_loops": "",
                            "preferences": ""
                        }
                except Exception as e:
                    # Fail gracefully - continue without memory insights
                    self.logger.warning(
                        "Memory synthesis failed (non-critical)",
                        correlation_id=correlation_id,
                        step="memory_synthesis",
                        error=str(e),
                        error_type=type(e).__name__
                    )
                    context["memory_insights"] = {
                        "communication_style": "",
                        "client_history": "",
                        "recurring_topics": "",
                        "open_loops": "",
                        "preferences": ""
                    }
                
                # Format memory context section for use in prompts
                context["memory_context_section"] = format_memory_context(context.get("memory_insights", {}))
                
                step_duration = (datetime.utcnow() - step_start).total_seconds() * 1000
                
                self.logger.info(
                    "Step 3: Memory retrieval completed",
                    correlation_id=correlation_id,
                    step="memory_retrieval",
                    duration_ms=step_duration,
                    memories_count=len(context.get("user_memories", []))
                )
                
                if debug:
                    intermediate_outputs["context"] = {
                        "user_memories_count": len(context.get("user_memories", [])),
                        "has_client_context": "client_context" in context,
                        "has_memory_insights": "memory_insights" in context
                    }
            except Exception as e:
                self.logger.error(
                    "Step 3: Memory retrieval failed",
                    correlation_id=correlation_id,
                    step="memory_retrieval",
                    error=str(e),
                    error_type=type(e).__name__
                )
                # Failure-safe: use empty context
                context = {}
                # Set empty memory insights on failure
                context["memory_insights"] = {
                    "communication_style": "",
                    "client_history": "",
                    "recurring_topics": "",
                    "open_loops": "",
                    "preferences": ""
                }
                # Format empty memory context section
                context["memory_context_section"] = format_memory_context(context.get("memory_insights", {}))
                if debug:
                    intermediate_outputs["context"] = {}
                    intermediate_outputs["memory_error"] = str(e)
            
            # Step 4: Data Preparation
            step_start = datetime.utcnow()
            self.logger.debug(
                "Step 4: Data preparation started",
                correlation_id=correlation_id,
                step="data_preparation"
            )
            
            try:
                prepared_data = self.data_preparator.extract_meeting_selection(
                    message,
                    extracted_info,
                    selected_meeting_id,
                    selected_calendar_event_id
                )
                step_duration = (datetime.utcnow() - step_start).total_seconds() * 1000
                
                self.logger.info(
                    "Step 4: Data preparation completed",
                    correlation_id=correlation_id,
                    step="data_preparation",
                    duration_ms=step_duration
                )
                
                if debug:
                    intermediate_outputs["prepared_data"] = prepared_data
            except Exception as e:
                self.logger.error(
                    "Step 4: Data preparation failed",
                    correlation_id=correlation_id,
                    step="data_preparation",
                    error=str(e),
                    error_type=type(e).__name__
                )
                # Failure-safe: use empty prepared data
                prepared_data = {}
                if debug:
                    intermediate_outputs["prepared_data"] = {}
                    intermediate_outputs["preparation_error"] = str(e)
            
            # Step 5: Integration Data Fetching
            step_start = datetime.utcnow()
            self.logger.debug(
                "Step 5: Integration data fetching started",
                correlation_id=correlation_id,
                step="integration_data_fetching"
            )
            
            try:
                integration_data = await self.tool_executor.prepare_integration_data(
                    intent,
                    prepared_data,
                    user_id,
                    client_id,
                    context
                )
                # TEMPORARY DEBUG: Log integration_data.meeting_id
                print(f"[AGENT DEBUG] integration_data.meeting_id = {integration_data.get('meeting_id')}")
                print(f"[AGENT DEBUG] integration_data.has_structured_data = {bool(integration_data.get('structured_data'))}")
                print(f"[AGENT DEBUG] user_id passed to prepare_integration_data = {user_id}")
                
                step_duration = (datetime.utcnow() - step_start).total_seconds() * 1000
                
                self.logger.info(
                    "Step 5: Integration data fetching completed",
                    correlation_id=correlation_id,
                    step="integration_data_fetching",
                    duration_ms=step_duration,
                    has_meeting_id=integration_data.get("meeting_id") is not None,
                    has_structured_data=integration_data.get("structured_data") is not None
                )
                
                if debug:
                    intermediate_outputs["integration_data"] = {
                        "has_meeting_id": integration_data.get("meeting_id") is not None,
                        "has_structured_data": integration_data.get("structured_data") is not None,
                        "has_error": "error" in integration_data,
                        "meeting_id": integration_data.get("meeting_id"),
                        "structured_data": integration_data.get("structured_data"),
                        "full_data": integration_data
                    }
            except Exception as e:
                self.logger.error(
                    "Step 5: Integration data fetching failed",
                    correlation_id=correlation_id,
                    step="integration_data_fetching",
                    error=str(e),
                    error_type=type(e).__name__
                )
                # Failure-safe: use empty integration data
                integration_data = {}
                if debug:
                    intermediate_outputs["integration_data"] = {}
                    intermediate_outputs["integration_error"] = str(e)
            
            # Step 6: Tool Execution
            step_start = datetime.utcnow()
            self.logger.debug(
                "Step 6: Tool execution started",
                correlation_id=correlation_id,
                step="tool_execution",
                tool_intent=intent
            )
            
            try:
                tool_output = await self.tool_executor.execute(
                    intent,
                    message,
                    context,
                    user_id,
                    client_id,
                    extracted_info,
                    prepared_data,
                    integration_data,
                    workflow=workflow
                )
                step_duration = (datetime.utcnow() - step_start).total_seconds() * 1000
                
                self.logger.info(
                    "Step 6: Tool execution completed",
                    correlation_id=correlation_id,
                    step="tool_execution",
                    duration_ms=step_duration,
                    tool_name=tool_output.get("tool_name") if tool_output else None,
                    has_error="error" in tool_output if tool_output else False
                )
                
                if debug:
                    intermediate_outputs["tool_output"] = {
                        "tool_name": tool_output.get("tool_name") if tool_output else None,
                        "has_result": "result" in tool_output if tool_output else False,
                        "has_error": "error" in tool_output if tool_output else False
                    }
            except Exception as e:
                self.logger.error(
                    "Step 6: Tool execution failed",
                    correlation_id=correlation_id,
                    step="tool_execution",
                    error=str(e),
                    error_type=type(e).__name__
                )
                # Failure-safe: use error tool output
                tool_output = {
                    "tool_name": intent,
                    "error": f"Tool execution failed: {str(e)}"
                }
                if debug:
                    intermediate_outputs["tool_output"] = tool_output
                    intermediate_outputs["tool_error"] = str(e)
            
            # Step 7: Output Synthesis
            step_start = datetime.utcnow()
            self.logger.debug(
                "Step 7: Output synthesis started",
                correlation_id=correlation_id,
                step="output_synthesis"
            )
            
            try:
                response = await self.output_synthesizer.synthesize(
                    message,
                    intent,
                    tool_output,
                    context
                )
                step_duration = (datetime.utcnow() - step_start).total_seconds() * 1000
                
                self.logger.info(
                    "Step 7: Output synthesis completed",
                    correlation_id=correlation_id,
                    step="output_synthesis",
                    duration_ms=step_duration,
                    response_length=len(response) if response else 0
                )
            except Exception as e:
                self.logger.error(
                    "Step 7: Output synthesis failed",
                    correlation_id=correlation_id,
                    step="output_synthesis",
                    error=str(e),
                    error_type=type(e).__name__
                )
                # Failure-safe: use graceful fallback message
                if tool_output and tool_output.get("error"):
                    response = f"I encountered an error while processing your request: {tool_output['error']}. Please try again or contact support."
                else:
                    response = "I apologize, but I encountered an error while processing your request. Please try again."
                if debug:
                    intermediate_outputs["synthesis_error"] = str(e)
            
            # Step 8: Memory Writing
            step_start = datetime.utcnow()
            self.logger.debug(
                "Step 8: Memory writing started",
                correlation_id=correlation_id,
                step="memory_writing"
            )
            
            try:
                await self.memory_writer.write(user_id, client_id, message, response, tool_output)
                step_duration = (datetime.utcnow() - step_start).total_seconds() * 1000
                
                self.logger.info(
                    "Step 8: Memory writing completed",
                    correlation_id=correlation_id,
                    step="memory_writing",
                    duration_ms=step_duration
                )
            except Exception as e:
                # Memory writing failures are non-critical, log but don't fail
                self.logger.warning(
                    "Step 8: Memory writing failed (non-critical)",
                    correlation_id=correlation_id,
                    step="memory_writing",
                    error=str(e),
                    error_type=type(e).__name__
                )
            
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
            
            total_duration = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            self.logger.info(
                "Agent pipeline completed",
                correlation_id=correlation_id,
                total_duration_ms=total_duration,
                intent=intent,
                tool_used=tool_output.get("tool_name") if tool_output else None
            )
            
            result = {
                "response": response,
                "tool_used": tool_output.get("tool_name") if tool_output else None,
                "meeting_options": meeting_options,
                "metadata": {
                    "intent": intent,
                    "confidence": intent_data.get("confidence", 0.0),
                    "workflow": workflow,
                    "correlation_id": correlation_id
                }
            }
            
            if debug:
                result["debug"] = intermediate_outputs
            
            return result
            
        except Exception as e:
            # Final safety net - should never reach here, but if it does, return graceful error
            total_duration = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            self.logger.error(
                "Agent pipeline failed catastrophically",
                correlation_id=correlation_id,
                total_duration_ms=total_duration,
                error=str(e),
                error_type=type(e).__name__
            )
            
            return {
                "response": "I apologize, but I encountered an unexpected error. Please try again or contact support.",
                "tool_used": None,
                "meeting_options": None,
                "metadata": {
                    "intent": "general",
                    "confidence": 0.0,
                    "workflow": {"steps": []},
                    "correlation_id": correlation_id,
                    "error": "Pipeline execution failed"
                },
                "debug": intermediate_outputs if debug else None
            }
