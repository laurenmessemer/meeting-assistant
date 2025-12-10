"""Tests for prerequisite checking logic (Step 3)."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from tests.integrations.test_integration_mocks import (
    build_mock_workflow,
    build_mock_context,
    build_mock_prepared_data,
    build_mock_integration_data
)


class TestPrerequisites:
    """Tests for prerequisite validation."""
    
    @pytest.mark.asyncio
    async def test_all_prerequisites_satisfied(self, tool_executor):
        """Test that execution continues when all prerequisites are satisfied."""
        # Arrange
        workflow = build_mock_workflow(
            required_data=["meeting_id", "client_id", "transcript"],
            steps=[{"action": "summarize", "tool": "summarization"}]
        )
        context = build_mock_context()
        prepared_data = build_mock_prepared_data(target_date=datetime(2024, 5, 1))
        integration_data = build_mock_integration_data(
            meeting_id=123,
            structured_data={"transcript": "Test transcript"}
        )
        client_id = 456
        
        # Mock _execute_with_plan to return success
        tool_executor._execute_with_plan = AsyncMock(return_value={
            "tool_name": "summarization",
            "result": {"summary": "Test summary"}
        })
        
        # Act
        result = await tool_executor.execute(
            "summarization",
            "Test message",
            context,
            1,
            client_id,
            {},
            prepared_data,
            integration_data,
            workflow=workflow
        )
        
        # Assert
        assert result is not None
        assert result.get("tool_name") == "summarization"
        tool_executor._execute_with_plan.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_missing_meeting_id_prerequisite(self, tool_executor):
        """Test that missing meeting_id prerequisite returns error."""
        # Arrange
        workflow = build_mock_workflow(
            required_data=["meeting_id"],
            steps=[{"action": "summarize", "tool": "summarization"}]
        )
        context = build_mock_context()
        prepared_data = build_mock_prepared_data()
        integration_data = build_mock_integration_data()  # No meeting_id
        
        # Act
        result = await tool_executor.execute(
            "summarization",
            "Test message",
            context,
            1,
            2,
            {},
            prepared_data,
            integration_data,
            workflow=workflow
        )
        
        # Assert
        assert result is not None
        assert result.get("tool_name") == "workflow"
        assert "error" in result
        assert "Missing prerequisites" in result["error"]
        assert "meeting_id" in result["error"]
        # _execute_with_plan should NOT be called
        assert not hasattr(tool_executor, '_execute_with_plan') or \
               not hasattr(tool_executor._execute_with_plan, 'call_count') or \
               tool_executor._execute_with_plan.call_count == 0
    
    @pytest.mark.asyncio
    async def test_missing_client_id_prerequisite(self, tool_executor):
        """Test that missing client_id prerequisite returns error."""
        # Arrange
        workflow = build_mock_workflow(
            required_data=["client_id"],
            steps=[{"action": "summarize", "tool": "summarization"}]
        )
        context = build_mock_context()
        prepared_data = build_mock_prepared_data()
        integration_data = build_mock_integration_data()
        client_id = None  # Missing client_id
        
        # Act
        result = await tool_executor.execute(
            "summarization",
            "Test message",
            context,
            1,
            client_id,
            {},
            prepared_data,
            integration_data,
            workflow=workflow
        )
        
        # Assert
        assert result is not None
        assert result.get("tool_name") == "workflow"
        assert "error" in result
        assert "Missing prerequisites" in result["error"]
        assert "client_id" in result["error"]
    
    @pytest.mark.asyncio
    async def test_missing_transcript_prerequisite(self, tool_executor):
        """Test that missing transcript prerequisite returns error."""
        # Arrange
        workflow = build_mock_workflow(
            required_data=["transcript"],
            steps=[{"action": "summarize", "tool": "summarization"}]
        )
        context = build_mock_context()
        prepared_data = build_mock_prepared_data()
        integration_data = build_mock_integration_data(
            structured_data={}  # No transcript
        )
        
        # Act
        result = await tool_executor.execute(
            "summarization",
            "Test message",
            context,
            1,
            2,
            {},
            prepared_data,
            integration_data,
            workflow=workflow
        )
        
        # Assert
        assert result is not None
        assert result.get("tool_name") == "workflow"
        assert "error" in result
        assert "Missing prerequisites" in result["error"]
        assert "transcript" in result["error"]
    
    @pytest.mark.asyncio
    async def test_unknown_prerequisite_ignored(self, tool_executor):
        """Test that unknown prerequisites are ignored."""
        # Arrange
        workflow = build_mock_workflow(
            required_data=["unknown_key", "meeting_id"],
            steps=[{"action": "summarize", "tool": "summarization"}]
        )
        context = build_mock_context()
        prepared_data = build_mock_prepared_data()
        integration_data = build_mock_integration_data(meeting_id=123)
        
        # Mock _execute_with_plan to return success
        tool_executor._execute_with_plan = AsyncMock(return_value={
            "tool_name": "summarization",
            "result": {"summary": "Test summary"}
        })
        
        # Act
        result = await tool_executor.execute(
            "summarization",
            "Test message",
            context,
            1,
            2,
            {},
            prepared_data,
            integration_data,
            workflow=workflow
        )
        
        # Assert
        assert result is not None
        assert result.get("tool_name") == "summarization"
        # Unknown key should not appear in error
        if "error" in result:
            assert "unknown_key" not in result["error"]
        tool_executor._execute_with_plan.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_prerequisites_with_fallback(self, tool_executor):
        """Test that prerequisites are checked before fallback execution."""
        # Arrange
        workflow = build_mock_workflow(
            required_data=["meeting_id"],
            steps=[{
                "action": "find_meeting",
                "tool": "meeting_finder",
                "fallback": {
                    "action": "resolve_meeting_from_calendar",
                    "conditions": ["no_db_match"]
                }
            }]
        )
        context = build_mock_context()
        prepared_data = build_mock_prepared_data()
        integration_data = build_mock_integration_data()  # No meeting_id
        
        # Act
        result = await tool_executor.execute(
            "summarization",
            "Test message",
            context,
            1,
            2,
            {},
            prepared_data,
            integration_data,
            workflow=workflow
        )
        
        # Assert
        assert result is not None
        assert result.get("tool_name") == "workflow"
        assert "error" in result
        assert "Missing prerequisites" in result["error"]
        assert "meeting_id" in result["error"]
        # Fallback should NOT be triggered (prerequisites checked first)

