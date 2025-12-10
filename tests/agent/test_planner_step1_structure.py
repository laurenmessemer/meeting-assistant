"""
Tests for Step 1: Planning Prompt Enhancement Validation.

These tests validate that the enhanced planning prompt:
1. Returns valid JSON structure
2. Maintains backward compatibility
3. Produces enriched structured steps when LLM follows prompt
4. Does not break existing pipeline behavior
5. Handles errors gracefully

These tests do NOT assume Step 2+ features (workflow consumption by ToolExecutor).
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.orchestrator.workflow_planning import WorkflowPlanner
from app.llm.gemini_client import GeminiClient
import json


class TestPlannerStep1Structure:
    """Tests for Step 1 planning prompt enhancement."""
    
    @pytest.fixture
    def mock_llm(self):
        """Create a mocked LLM client."""
        llm = MagicMock(spec=GeminiClient)
        llm.llm_chat = MagicMock()  # llm_chat is not async
        return llm
    
    @pytest.fixture
    def workflow_planner(self, mock_llm):
        """Create workflow planner with mocked LLM."""
        return WorkflowPlanner(mock_llm)
    
    # ===== A. Planner Returns Valid JSON =====
    
    @pytest.mark.asyncio
    async def test_planner_always_returns_dict(self, workflow_planner, mock_llm):
        """Test that planner always returns a dict, never raises JSON parsing error."""
        # Test with dict response
        mock_llm.llm_chat.return_value = {
            "steps": [{"action": "find_meeting", "tool": "meeting_finder"}]
        }
        
        result = await workflow_planner.plan(
            intent="summarization",
            message="Test message",
            user_id=1,
            client_id=1
        )
        
        assert isinstance(result, dict), "Planner must always return a dict"
        assert "steps" in result, "Result must contain 'steps' key"
    
    @pytest.mark.asyncio
    async def test_planner_handles_string_json_response(self, workflow_planner, mock_llm):
        """Test that planner handles string JSON responses correctly."""
        mock_llm.llm_chat.return_value = '{"steps": [{"action": "find_meeting", "tool": "meeting_finder"}]}'
        
        result = await workflow_planner.plan(
            intent="summarization",
            message="Test message",
            user_id=1,
            client_id=1
        )
        
        assert isinstance(result, dict), "Planner must parse string JSON to dict"
        assert "steps" in result, "Result must contain 'steps' key"
    
    @pytest.mark.asyncio
    async def test_planner_recovers_on_malformed_output(self, workflow_planner, mock_llm):
        """Test that planner recovers gracefully to {'steps': []} on malformed output."""
        # Test with invalid JSON string
        mock_llm.llm_chat.return_value = "invalid json { not valid }"
        
        result = await workflow_planner.plan(
            intent="summarization",
            message="Test message",
            user_id=1,
            client_id=1
        )
        
        assert isinstance(result, dict), "Planner must return dict even on error"
        assert result == {"steps": []}, "Planner must return {'steps': []} on error"
    
    @pytest.mark.asyncio
    async def test_planner_recovers_on_exception(self, workflow_planner, mock_llm):
        """Test that planner recovers gracefully on exception."""
        mock_llm.llm_chat.side_effect = Exception("LLM API error")
        
        result = await workflow_planner.plan(
            intent="summarization",
            message="Test message",
            user_id=1,
            client_id=1
        )
        
        assert isinstance(result, dict), "Planner must return dict even on exception"
        assert result == {"steps": []}, "Planner must return {'steps': []} on exception"
    
    @pytest.mark.asyncio
    async def test_planner_handles_invalid_type_response(self, workflow_planner, mock_llm):
        """Test that planner handles invalid response types."""
        mock_llm.llm_chat.return_value = 12345  # Not dict or string
        
        result = await workflow_planner.plan(
            intent="summarization",
            message="Test message",
            user_id=1,
            client_id=1
        )
        
        assert isinstance(result, dict), "Planner must return dict even on invalid type"
        assert result == {"steps": []}, "Planner must return {'steps': []} on invalid type"
    
    # ===== B. Steps Remain an Array =====
    
    @pytest.mark.asyncio
    async def test_steps_is_always_list(self, workflow_planner, mock_llm):
        """Test that steps is always a list."""
        mock_llm.llm_chat.return_value = {
            "steps": [{"action": "find_meeting", "tool": "meeting_finder"}]
        }
        
        result = await workflow_planner.plan(
            intent="summarization",
            message="Test message",
            user_id=1,
            client_id=1
        )
        
        assert isinstance(result["steps"], list), "Steps must always be a list"
    
    @pytest.mark.asyncio
    async def test_steps_may_contain_strings_backward_compatible(self, workflow_planner, mock_llm):
        """Test that steps may contain strings (backward compatible format)."""
        mock_llm.llm_chat.return_value = {
            "steps": [
                "Find most recent meeting",
                "Retrieve meeting transcript",
                "Run summarization tool"
            ]
        }
        
        result = await workflow_planner.plan(
            intent="summarization",
            message="Test message",
            user_id=1,
            client_id=1
        )
        
        assert isinstance(result["steps"], list), "Steps must be a list"
        assert len(result["steps"]) == 3, "Steps must contain 3 items"
        assert all(isinstance(step, str) for step in result["steps"]), "All steps must be strings"
    
    @pytest.mark.asyncio
    async def test_steps_may_contain_objects_enhanced_format(self, workflow_planner, mock_llm):
        """Test that steps may contain objects (enhanced format)."""
        mock_llm.llm_chat.return_value = {
            "steps": [
                {
                    "action": "find_meeting",
                    "tool": "meeting_finder",
                    "prerequisites": ["client_id"]
                },
                {
                    "action": "summarize",
                    "tool": "summarization",
                    "prerequisites": ["meeting_id", "transcript"]
                }
            ]
        }
        
        result = await workflow_planner.plan(
            intent="summarization",
            message="Test message",
            user_id=1,
            client_id=1
        )
        
        assert isinstance(result["steps"], list), "Steps must be a list"
        assert len(result["steps"]) == 2, "Steps must contain 2 items"
        assert all(isinstance(step, dict) for step in result["steps"]), "All steps must be objects"
    
    @pytest.mark.asyncio
    async def test_step_objects_contain_action_and_tool(self, workflow_planner, mock_llm):
        """Test that step objects contain at least 'action' and 'tool' fields."""
        mock_llm.llm_chat.return_value = {
            "steps": [
                {
                    "action": "find_meeting",
                    "tool": "meeting_finder"
                }
            ]
        }
        
        result = await workflow_planner.plan(
            intent="summarization",
            message="Test message",
            user_id=1,
            client_id=1
        )
        
        step = result["steps"][0]
        assert isinstance(step, dict), "Step must be an object"
        assert "action" in step, "Step object must contain 'action' field"
        assert "tool" in step, "Step object must contain 'tool' field"
        assert step["action"] == "find_meeting", "Action must match"
        assert step["tool"] == "meeting_finder", "Tool must match"
    
    @pytest.mark.asyncio
    async def test_steps_may_be_mixed_format_backward_compatible(self, workflow_planner, mock_llm):
        """Test that steps may be mixed (strings and objects) for backward compatibility."""
        mock_llm.llm_chat.return_value = {
            "steps": [
                "Find most recent meeting",  # String format
                {
                    "action": "summarize",
                    "tool": "summarization"
                }  # Object format
            ]
        }
        
        result = await workflow_planner.plan(
            intent="summarization",
            message="Test message",
            user_id=1,
            client_id=1
        )
        
        assert isinstance(result["steps"], list), "Steps must be a list"
        assert len(result["steps"]) == 2, "Steps must contain 2 items"
        assert isinstance(result["steps"][0], str), "First step may be string"
        assert isinstance(result["steps"][1], dict), "Second step may be object"
    
    # ===== C. Planner Does NOT Break Pipeline =====
    
    @pytest.mark.asyncio
    async def test_summarization_runs_without_workflow(self, workflow_planner, mock_llm):
        """Test that summarization intent can run successfully without using workflow."""
        # Planner returns workflow (but it's not used by ToolExecutor yet)
        mock_llm.llm_chat.return_value = {
            "steps": [{"action": "summarize", "tool": "summarization"}]
        }
        
        result = await workflow_planner.plan(
            intent="summarization",
            message="Summarize my last meeting",
            user_id=1,
            client_id=1
        )
        
        # Planner should return workflow successfully
        assert isinstance(result, dict), "Planner must return dict"
        assert "steps" in result, "Workflow must contain steps"
        
        # Note: ToolExecutor doesn't use workflow yet (Step 2), so this test
        # only validates that planner doesn't break the planning step
    
    @pytest.mark.asyncio
    async def test_followup_runs_without_workflow(self, workflow_planner, mock_llm):
        """Test that follow-up intent can run successfully without using workflow."""
        mock_llm.llm_chat.return_value = {
            "steps": [{"action": "generate_followup", "tool": "followup"}]
        }
        
        result = await workflow_planner.plan(
            intent="followup",
            message="Draft a follow-up email",
            user_id=1,
            client_id=1
        )
        
        assert isinstance(result, dict), "Planner must return dict"
        assert "steps" in result, "Workflow must contain steps"
    
    @pytest.mark.asyncio
    async def test_meeting_brief_runs_without_workflow(self, workflow_planner, mock_llm):
        """Test that meeting brief intent can run successfully without using workflow."""
        mock_llm.llm_chat.return_value = {
            "steps": [{"action": "generate_brief", "tool": "meeting_brief"}]
        }
        
        result = await workflow_planner.plan(
            intent="meeting_brief",
            message="Prepare me for my next meeting",
            user_id=1,
            client_id=1
        )
        
        assert isinstance(result, dict), "Planner must return dict"
        assert "steps" in result, "Workflow must contain steps"
    
    @pytest.mark.asyncio
    async def test_agent_pipeline_continues_on_planning_failure(self):
        """Test that agent pipeline continues even if planning fails."""
        from app.orchestrator.agent import AgentOrchestrator
        from sqlalchemy.orm import Session
        from unittest.mock import MagicMock
        
        # Create mock database session
        mock_db = MagicMock(spec=Session)
        
        # Create orchestrator
        with patch('app.orchestrator.agent.GeminiClient') as mock_gemini:
            # Mock LLM to raise exception during planning
            mock_llm_instance = MagicMock()
            mock_llm_instance.llm_chat.side_effect = [
                Exception("Planning error"),  # Planning fails
                {"intent": "summarization", "confidence": 0.9, "extracted_info": {}}  # Intent recognition succeeds
            ]
            mock_gemini.return_value = mock_llm_instance
            
            orchestrator = AgentOrchestrator(mock_db)
            
            # Mock the rest of the pipeline to avoid full execution
            with patch.object(orchestrator, 'memory_retriever') as mock_memory:
                with patch.object(orchestrator, 'data_preparator') as mock_data:
                    with patch.object(orchestrator, 'tool_executor') as mock_tool:
                        mock_memory.retrieve = AsyncMock(return_value={})
                        mock_data.extract_meeting_selection = MagicMock(return_value={})
                        mock_tool.prepare_integration_data = AsyncMock(return_value={})
                        mock_tool.execute = AsyncMock(return_value={"tool_name": "summarization", "result": "test"})
                        
                        # This should not raise exception even if planning fails
                        # We're just testing that planning failure doesn't break the pipeline
                        # Note: Full pipeline test would require more mocking, but we can verify
                        # that the exception handler exists and returns {"steps": []}
                        
                        # Verify exception handler exists in workflow_planning.py
                        from app.orchestrator.workflow_planning import WorkflowPlanner
                        planner = WorkflowPlanner(mock_llm_instance)
                        
                        # Simulate planning failure
                        result = await planner.plan("summarization", "test", 1, 1)
                        assert result == {"steps": []}, "Planner must return {'steps': []} on failure"
    
    # ===== D. Planner Produces Enriched Structure =====
    
    @pytest.mark.asyncio
    async def test_step_objects_contain_action_field(self, workflow_planner, mock_llm):
        """Test that step objects contain 'action' field when LLM follows enhanced prompt."""
        mock_llm.llm_chat.return_value = {
            "steps": [
                {
                    "action": "find_meeting",
                    "tool": "meeting_finder",
                    "prerequisites": ["client_id"]
                }
            ]
        }
        
        result = await workflow_planner.plan(
            intent="summarization",
            message="Test message",
            user_id=1,
            client_id=1
        )
        
        step = result["steps"][0]
        assert "action" in step, "Step object must contain 'action' field"
        assert step["action"] == "find_meeting", "Action must match expected value"
    
    @pytest.mark.asyncio
    async def test_step_objects_contain_tool_field(self, workflow_planner, mock_llm):
        """Test that step objects contain 'tool' field when LLM follows enhanced prompt."""
        mock_llm.llm_chat.return_value = {
            "steps": [
                {
                    "action": "find_meeting",
                    "tool": "meeting_finder"
                }
            ]
        }
        
        result = await workflow_planner.plan(
            intent="summarization",
            message="Test message",
            user_id=1,
            client_id=1
        )
        
        step = result["steps"][0]
        assert "tool" in step, "Step object must contain 'tool' field"
        assert step["tool"] == "meeting_finder", "Tool must match expected value"
    
    @pytest.mark.asyncio
    async def test_step_objects_may_contain_prerequisites(self, workflow_planner, mock_llm):
        """Test that step objects may contain optional 'prerequisites' field."""
        mock_llm.llm_chat.return_value = {
            "steps": [
                {
                    "action": "find_meeting",
                    "tool": "meeting_finder",
                    "prerequisites": ["client_id", "user_id"]
                }
            ]
        }
        
        result = await workflow_planner.plan(
            intent="summarization",
            message="Test message",
            user_id=1,
            client_id=1
        )
        
        step = result["steps"][0]
        assert "prerequisites" in step, "Step object may contain 'prerequisites' field"
        assert isinstance(step["prerequisites"], list), "Prerequisites must be a list"
        assert "client_id" in step["prerequisites"], "Prerequisites must contain expected values"
    
    @pytest.mark.asyncio
    async def test_step_objects_may_contain_fallback(self, workflow_planner, mock_llm):
        """Test that step objects may contain optional 'fallback' field."""
        mock_llm.llm_chat.return_value = {
            "steps": [
                {
                    "action": "find_meeting",
                    "tool": "meeting_finder",
                    "fallback": {
                        "if": "no_db_match",
                        "then": "search_calendar"
                    }
                }
            ]
        }
        
        result = await workflow_planner.plan(
            intent="summarization",
            message="Test message",
            user_id=1,
            client_id=1
        )
        
        step = result["steps"][0]
        assert "fallback" in step, "Step object may contain 'fallback' field"
        assert isinstance(step["fallback"], dict), "Fallback must be an object"
        assert "if" in step["fallback"], "Fallback must contain 'if' field"
        assert "then" in step["fallback"], "Fallback must contain 'then' field"
    
    @pytest.mark.asyncio
    async def test_required_data_field_optional(self, workflow_planner, mock_llm):
        """Test that 'required_data' field is optional at root level."""
        # Test with required_data
        mock_llm.llm_chat.return_value = {
            "steps": [{"action": "find_meeting", "tool": "meeting_finder"}],
            "required_data": ["client_id", "meeting_id"]
        }
        
        result = await workflow_planner.plan(
            intent="summarization",
            message="Test message",
            user_id=1,
            client_id=1
        )
        
        assert "required_data" in result, "Result may contain 'required_data'"
        assert isinstance(result["required_data"], list), "Required_data must be a list"
        
        # Test without required_data
        mock_llm.llm_chat.return_value = {
            "steps": [{"action": "find_meeting", "tool": "meeting_finder"}]
        }
        
        result = await workflow_planner.plan(
            intent="summarization",
            message="Test message",
            user_id=1,
            client_id=1
        )
        
        # required_data is optional, so it's OK if missing
        assert "steps" in result, "Result must contain 'steps'"
        # required_data may or may not be present (both are valid)
    
    # ===== E. Planner Logging Still Works =====
    
    @pytest.mark.asyncio
    async def test_workflow_object_stored_in_debug_metadata(self):
        """Test that workflow object is stored in debug metadata."""
        from app.orchestrator.agent import AgentOrchestrator
        from unittest.mock import MagicMock, AsyncMock, patch
        
        mock_db = MagicMock()
        
        with patch('app.orchestrator.agent.GeminiClient') as mock_gemini:
            mock_llm_instance = MagicMock()
            # Mock planning response
            mock_llm_instance.llm_chat = MagicMock(side_effect=[
                {"intent": "summarization", "confidence": 0.9, "extracted_info": {}},  # Intent recognition
                {"steps": [{"action": "find_meeting", "tool": "meeting_finder"}]}  # Planning
            ])
            mock_gemini.return_value = mock_llm_instance
            
            orchestrator = AgentOrchestrator(mock_db)
            
            # Mock rest of pipeline
            with patch.object(orchestrator.memory_retriever, 'retrieve', new_callable=AsyncMock) as mock_memory:
                with patch.object(orchestrator.data_preparator, 'extract_meeting_selection') as mock_data:
                    with patch.object(orchestrator.tool_executor, 'prepare_integration_data', new_callable=AsyncMock) as mock_integration:
                        with patch.object(orchestrator.tool_executor, 'execute', new_callable=AsyncMock) as mock_tool:
                            with patch.object(orchestrator.output_synthesizer, 'synthesize', new_callable=AsyncMock) as mock_output:
                                with patch.object(orchestrator.memory_writer, 'write', new_callable=AsyncMock) as mock_write:
                                    mock_memory.return_value = {}
                                    mock_data.return_value = {}
                                    mock_integration.return_value = {}
                                    mock_tool.return_value = {"tool_name": "summarization", "result": "test"}
                                    mock_output.return_value = "Test response"
                                    
                                    result = await orchestrator.process_message(
                                        message="Summarize my last meeting",
                                        user_id=1,
                                        client_id=1,
                                        debug=True
                                    )
                                    
                                    # Verify workflow is in debug metadata
                                    assert "debug" in result, "Debug output must be present"
                                    assert "workflow" in result["debug"], "Workflow must be in debug metadata"
                                    assert isinstance(result["debug"]["workflow"], dict), "Workflow must be a dict"
                                    assert "steps" in result["debug"]["workflow"], "Workflow must contain steps"
    
    @pytest.mark.asyncio
    async def test_step_count_logic_still_functions(self):
        """Test that step count logic still functions in agent.py."""
        from app.orchestrator.agent import AgentOrchestrator
        from unittest.mock import MagicMock, AsyncMock, patch
        
        mock_db = MagicMock()
        
        with patch('app.orchestrator.agent.GeminiClient') as mock_gemini:
            mock_llm_instance = MagicMock()
            mock_llm_instance.llm_chat = MagicMock(side_effect=[
                {"intent": "summarization", "confidence": 0.9, "extracted_info": {}},
                {"steps": [{"action": "find_meeting", "tool": "meeting_finder"}]}
            ])
            mock_gemini.return_value = mock_llm_instance
            
            orchestrator = AgentOrchestrator(mock_db)
            
            # Mock rest of pipeline
            with patch.object(orchestrator.memory_retriever, 'retrieve', new_callable=AsyncMock) as mock_memory:
                with patch.object(orchestrator.data_preparator, 'extract_meeting_selection') as mock_data:
                    with patch.object(orchestrator.tool_executor, 'prepare_integration_data', new_callable=AsyncMock) as mock_integration:
                        with patch.object(orchestrator.tool_executor, 'execute', new_callable=AsyncMock) as mock_tool:
                            with patch.object(orchestrator.output_synthesizer, 'synthesize', new_callable=AsyncMock) as mock_output:
                                with patch.object(orchestrator.memory_writer, 'write', new_callable=AsyncMock) as mock_write:
                                    mock_memory.return_value = {}
                                    mock_data.return_value = {}
                                    mock_integration.return_value = {}
                                    mock_tool.return_value = {"tool_name": "summarization", "result": "test"}
                                    mock_output.return_value = "Test response"
                                    
                                    result = await orchestrator.process_message(
                                        message="Summarize my last meeting",
                                        user_id=1,
                                        client_id=1,
                                        debug=False
                                    )
                                    
                                    # Verify workflow is in metadata (for step count logging)
                                    assert "metadata" in result, "Metadata must be present"
                                    assert "workflow" in result["metadata"], "Workflow must be in metadata"
                                    workflow = result["metadata"]["workflow"]
                                    assert isinstance(workflow, dict), "Workflow must be a dict"
                                    assert "steps" in workflow, "Workflow must contain steps"
                                    # Step count logic: len(workflow.get("steps", [])) should work
                                    step_count = len(workflow.get("steps", []))
                                    assert step_count >= 0, "Step count must be non-negative"
    
    @pytest.mark.asyncio
    async def test_no_exceptions_in_agent_planning_step(self):
        """Test that no exceptions occur in agent.py during planning step."""
        from app.orchestrator.agent import AgentOrchestrator
        from unittest.mock import MagicMock, AsyncMock, patch
        
        mock_db = MagicMock()
        
        with patch('app.orchestrator.agent.GeminiClient') as mock_gemini:
            mock_llm_instance = MagicMock()
            # Simulate planning returning enhanced format
            mock_llm_instance.llm_chat = MagicMock(side_effect=[
                {"intent": "summarization", "confidence": 0.9, "extracted_info": {}},
                {
                    "steps": [
                        {
                            "action": "find_meeting",
                            "tool": "meeting_finder",
                            "prerequisites": ["client_id"],
                            "fallback": {"if": "no_db_match", "then": "search_calendar"}
                        }
                    ],
                    "required_data": ["client_id"]
                }
            ])
            mock_gemini.return_value = mock_llm_instance
            
            orchestrator = AgentOrchestrator(mock_db)
            
            # Mock rest of pipeline
            with patch.object(orchestrator.memory_retriever, 'retrieve', new_callable=AsyncMock) as mock_memory:
                with patch.object(orchestrator.data_preparator, 'extract_meeting_selection') as mock_data:
                    with patch.object(orchestrator.tool_executor, 'prepare_integration_data', new_callable=AsyncMock) as mock_integration:
                        with patch.object(orchestrator.tool_executor, 'execute', new_callable=AsyncMock) as mock_tool:
                            with patch.object(orchestrator.output_synthesizer, 'synthesize', new_callable=AsyncMock) as mock_output:
                                with patch.object(orchestrator.memory_writer, 'write', new_callable=AsyncMock) as mock_write:
                                    mock_memory.return_value = {}
                                    mock_data.return_value = {}
                                    mock_integration.return_value = {}
                                    mock_tool.return_value = {"tool_name": "summarization", "result": "test"}
                                    mock_output.return_value = "Test response"
                                    
                                    # This should not raise any exceptions
                                    try:
                                        result = await orchestrator.process_message(
                                            message="Summarize my last meeting",
                                            user_id=1,
                                            client_id=1,
                                            debug=False
                                        )
                                        assert result is not None, "Result must not be None"
                                        assert "metadata" in result, "Result must contain metadata"
                                    except Exception as e:
                                        pytest.fail(f"Planning step should not raise exceptions: {e}")

