"""Tests for backward compatibility with legacy execution paths."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from tests.integrations.test_integration_mocks import (
    build_mock_context,
    build_mock_prepared_data,
    build_mock_integration_data,
    build_mock_meeting
)


class TestBackwardCompatibility:
    """Tests ensuring legacy execution paths remain functional."""
    
    @pytest.mark.asyncio
    async def test_no_workflow_legacy_path(self, tool_executor, mock_memory_repo, mock_tools):
        """Test that no workflow triggers legacy routing."""
        # Arrange
        intent = "summarization"
        message = "Summarize my meeting"
        context = build_mock_context()
        user_id = 1
        client_id = 2
        extracted_info = {}
        prepared_data = build_mock_prepared_data()
        integration_data = build_mock_integration_data(
            meeting_id=123,
            structured_data={"transcript": "Test transcript", "has_transcript": True}
        )
        workflow = None  # No workflow
        
        # Mock meeting exists in database
        from tests.integrations.test_integration_mocks import build_mock_meeting
        mock_meeting = build_mock_meeting(id=123, transcript="Test transcript")
        mock_memory_repo.get_meeting_by_id.return_value = mock_meeting
        
        # Mock tool execution
        mock_tools["summarization"].summarize_meeting = AsyncMock(return_value={
            "tool_name": "summarization",
            "result": {"summary": "Test summary"}
        })
        
        # Act
        result = await tool_executor.execute(
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
        
        # Assert
        assert result is not None
        assert result.get("tool_name") == "summarization"
        assert "result" in result
        assert "workflow" not in result
        assert "step_results" not in result
        assert "execution_trace" not in result
        mock_tools["summarization"].summarize_meeting.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_empty_workflow_legacy_path(self, tool_executor, mock_memory_repo, mock_tools):
        """Test that empty workflow triggers legacy routing."""
        # Arrange
        intent = "followup"
        message = "Generate follow-up"
        context = build_mock_context()
        user_id = 1
        client_id = 2
        extracted_info = {}
        prepared_data = build_mock_prepared_data()
        integration_data = build_mock_integration_data(
            meeting_id=123,
            structured_data={"meeting_summary": "Test summary"}
        )
        workflow = {"steps": []}  # Empty workflow
        
        # Mock meeting exists in database
        from tests.integrations.test_integration_mocks import build_mock_meeting
        mock_meeting = build_mock_meeting(id=123, summary="Test summary")
        mock_memory_repo.get_meeting_by_id.return_value = mock_meeting
        
        # Mock tool execution
        mock_tools["followup"].generate_followup = AsyncMock(return_value={
            "tool_name": "followup",
            "result": {"email": "Test email"}
        })
        
        # Act
        result = await tool_executor.execute(
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
        
        # Assert
        assert result is not None
        assert result.get("tool_name") == "followup"
        assert "result" in result
        assert "workflow" not in result
        assert "step_results" not in result
        mock_tools["followup"].generate_followup.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_invalid_workflow_legacy_path(self, tool_executor, mock_tools):
        """Test that invalid workflow triggers legacy routing."""
        # Arrange
        intent = "meeting_brief"
        message = "Generate brief"
        context = build_mock_context()
        user_id = 1
        client_id = 2
        extracted_info = {}
        prepared_data = build_mock_prepared_data()
        integration_data = build_mock_integration_data(
            structured_data={"client_name": "Test Client"}
        )
        workflow = {"invalid": "structure", "steps": "not_a_list"}  # Invalid workflow
        
        # Mock tool execution
        mock_tools["meeting_brief"].generate_brief = AsyncMock(return_value={
            "tool_name": "meeting_brief",
            "result": {"brief": "Test brief"}
        })
        
        # Act
        result = await tool_executor.execute(
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
        
        # Assert
        assert result is not None
        assert result.get("tool_name") == "meeting_brief"
        assert "result" in result
        assert "workflow" not in result
        assert "step_results" not in result
        mock_tools["meeting_brief"].generate_brief.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_legacy_tools_functional(self, tool_executor, mock_memory_repo, mock_tools):
        """Test that all legacy tools work exactly as before."""
        # Arrange
        context = build_mock_context()
        user_id = 1
        client_id = 2
        extracted_info = {}
        prepared_data = build_mock_prepared_data()
        workflow = None  # No workflow
        
        from tests.integrations.test_integration_mocks import build_mock_meeting
        
        # Test Summarization
        integration_data_summarization = build_mock_integration_data(
            meeting_id=123,
            structured_data={"transcript": "Test transcript", "has_transcript": True}
        )
        mock_meeting_summarization = build_mock_meeting(id=123, transcript="Test transcript")
        mock_memory_repo.get_meeting_by_id.return_value = mock_meeting_summarization
        mock_tools["summarization"].summarize_meeting = AsyncMock(return_value={
            "tool_name": "summarization",
            "result": {"summary": "Test summary", "decisions": []}
        })
        
        result_summarization = await tool_executor.execute(
            "summarization",
            "Summarize",
            context,
            user_id,
            client_id,
            extracted_info,
            prepared_data,
            integration_data_summarization,
            workflow=workflow
        )
        
        assert result_summarization.get("tool_name") == "summarization"
        assert "result" in result_summarization
        assert result_summarization.get("result", {}).get("summary") == "Test summary"
        
        # Test Follow-up
        integration_data_followup = build_mock_integration_data(
            meeting_id=123,
            structured_data={"meeting_summary": "Test summary"}
        )
        mock_meeting_followup = build_mock_meeting(id=123, summary="Test summary")
        mock_memory_repo.get_meeting_by_id.return_value = mock_meeting_followup
        mock_tools["followup"].generate_followup = AsyncMock(return_value={
            "tool_name": "followup",
            "result": {"email": "Test email"}
        })
        
        result_followup = await tool_executor.execute(
            "followup",
            "Follow-up",
            context,
            user_id,
            client_id,
            extracted_info,
            prepared_data,
            integration_data_followup,
            workflow=workflow
        )
        
        assert result_followup.get("tool_name") == "followup"
        assert "result" in result_followup
        assert result_followup["result"].get("email") == "Test email"
        
        # Test Meeting Brief
        integration_data_brief = build_mock_integration_data(
            structured_data={"client_name": "Test Client"}
        )
        mock_tools["meeting_brief"].generate_brief = AsyncMock(return_value={
            "tool_name": "meeting_brief",
            "result": {"brief": "Test brief"}
        })
        
        result_brief = await tool_executor.execute(
            "meeting_brief",
            "Brief",
            context,
            user_id,
            client_id,
            extracted_info,
            prepared_data,
            integration_data_brief,
            workflow=workflow
        )
        
        assert result_brief.get("tool_name") == "meeting_brief"
        assert "result" in result_brief
        assert result_brief["result"].get("brief") == "Test brief"

