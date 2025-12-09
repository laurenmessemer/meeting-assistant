"""Tests for workflow planner with mocked LLM."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from app.orchestrator.workflow_planning import WorkflowPlanner
from app.llm.gemini_client import GeminiClient


class TestWorkflowPlanner:
    """Tests for workflow planning with mocked LLM."""
    
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
    
    @pytest.mark.asyncio
    async def test_summarization_workflow_steps(self, workflow_planner, mock_llm):
        """Test that summarization intent generates correct workflow steps."""
        mock_llm.llm_chat.return_value = {
            "steps": [
                "Find most recent meeting",
                "Retrieve meeting transcript",
                "Retrieve HubSpot client info",
                "Retrieve memory context",
                "Run summarization tool"
            ],
            "required_data": ["transcript", "client_info", "memory_context"]
        }
        
        result = await workflow_planner.plan(
            intent="summarization",
            message="Summarize my last meeting",
            user_id=1,
            client_id=1
        )
        
        assert "steps" in result
        assert len(result["steps"]) == 5
        assert "Find most recent meeting" in result["steps"]
        assert "Retrieve meeting transcript" in result["steps"]
        assert "Run summarization tool" in result["steps"]
        mock_llm.llm_chat.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_meeting_brief_workflow_steps(self, workflow_planner, mock_llm):
        """Test that meeting_brief intent generates correct workflow steps."""
        mock_llm.llm_chat.return_value = {
            "steps": [
                "Find next meeting",
                "Retrieve calendar event details",
                "Retrieve HubSpot client info",
                "Retrieve previous meeting summary",
                "Run meeting brief tool"
            ],
            "required_data": ["calendar_event", "client_info", "previous_summary"]
        }
        
        result = await workflow_planner.plan(
            intent="meeting_brief",
            message="Prepare me for my next meeting",
            user_id=1,
            client_id=1
        )
        
        assert "steps" in result
        assert len(result["steps"]) == 5
        assert "Find next meeting" in result["steps"]
        assert "Run meeting brief tool" in result["steps"]
    
    @pytest.mark.asyncio
    async def test_followup_workflow_steps(self, workflow_planner, mock_llm):
        """Test that followup intent generates correct workflow steps."""
        mock_llm.llm_chat.return_value = {
            "steps": [
                "Find most recent meeting",
                "Retrieve meeting summary",
                "Retrieve decisions and action items",
                "Retrieve HubSpot client info",
                "Run followup tool"
            ],
            "required_data": ["meeting_summary", "decisions", "action_items", "client_info"]
        }
        
        result = await workflow_planner.plan(
            intent="followup",
            message="Draft a follow-up email",
            user_id=1,
            client_id=1
        )
        
        assert "steps" in result
        assert len(result["steps"]) == 5
        assert "Find most recent meeting" in result["steps"]
        assert "Run followup tool" in result["steps"]
    
    @pytest.mark.asyncio
    async def test_steps_ordered_correctly(self, workflow_planner, mock_llm):
        """Test that workflow steps are ordered correctly."""
        mock_llm.llm_chat.return_value = {
            "steps": [
                "Step 1: Find meeting",
                "Step 2: Retrieve data",
                "Step 3: Execute tool"
            ]
        }
        
        result = await workflow_planner.plan(
            intent="summarization",
            message="Summarize meeting",
            user_id=1,
            client_id=1
        )
        
        steps = result["steps"]
        assert len(steps) == 3
        # Steps should be in order
        assert steps[0] == "Step 1: Find meeting"
        assert steps[1] == "Step 2: Retrieve data"
        assert steps[2] == "Step 3: Execute tool"
    
    @pytest.mark.asyncio
    async def test_error_handling_returns_empty_steps(self, workflow_planner, mock_llm):
        """Test that exceptions return empty steps."""
        mock_llm.llm_chat.side_effect = Exception("LLM API error")
        
        result = await workflow_planner.plan(
            intent="summarization",
            message="Any message",
            user_id=1,
            client_id=1
        )
        
        assert result == {"steps": []}
    
    @pytest.mark.asyncio
    async def test_string_response_parsing(self, workflow_planner, mock_llm):
        """Test that string JSON responses are parsed correctly."""
        mock_llm.llm_chat.return_value = '{"steps": ["Step 1", "Step 2"]}'
        
        result = await workflow_planner.plan(
            intent="summarization",
            message="Any message",
            user_id=1,
            client_id=1
        )
        
        assert "steps" in result
        assert len(result["steps"]) == 2
    
    @pytest.mark.asyncio
    async def test_required_data_included(self, workflow_planner, mock_llm):
        """Test that workflow includes required data fields."""
        mock_llm.llm_chat.return_value = {
            "steps": ["Step 1", "Step 2"],
            "required_data": ["transcript", "client_info"]
        }
        
        result = await workflow_planner.plan(
            intent="summarization",
            message="Summarize meeting",
            user_id=1,
            client_id=1
        )
        
        assert "required_data" in result
        assert "transcript" in result["required_data"]
        assert "client_info" in result["required_data"]

