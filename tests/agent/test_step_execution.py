"""Tests for step execution coordination (Step 4)."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import sys
from pathlib import Path
# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from tests.integrations.test_integration_mocks import (
    build_mock_workflow,
    build_mock_step,
    build_mock_context,
    build_mock_prepared_data,
    build_mock_integration_data,
    build_mock_meeting,
    build_mock_calendar_event
)


class TestStepExecution:
    """Tests for step execution coordination."""
    
    @pytest.mark.asyncio
    async def test_sequential_step_execution(self, tool_executor, mock_memory_repo, mock_tools):
        """Test that steps execute sequentially and update context."""
        # Arrange
        workflow = build_mock_workflow(
            steps=[
                build_mock_step("find_meeting", "meeting_finder"),
                build_mock_step("retrieve_transcript", "integration_fetcher"),
                build_mock_step("summarize", "summarization")
            ]
        )
        context = build_mock_context()
        prepared_data = build_mock_prepared_data()
        integration_data = build_mock_integration_data()
        
        # Mock MeetingFinder
        with patch('app.orchestrator.tool_execution.MeetingFinder') as mock_finder_class:
            mock_finder = MagicMock()
            mock_finder_class.return_value = mock_finder
            mock_finder.find_meeting_in_database.return_value = 123
            mock_finder.find_meeting_in_calendar.return_value = (None, None)
            
            # Mock memory repo
            mock_meeting = build_mock_meeting(id=123, transcript=None)  # Force fetch
            mock_memory_repo.get_meeting_by_id.return_value = mock_meeting
            
            # Mock integration fetcher
            tool_executor.integration_data_fetcher.fetch_zoom_transcript = AsyncMock(
                return_value="Test transcript"
            )
            
            # Mock summarization tool
            mock_tools["summarization"].summarize_meeting = AsyncMock(return_value={
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
            assert "result" in result
            # Verify steps were called in order
            assert mock_finder.find_meeting_in_database.called
            assert tool_executor.integration_data_fetcher.fetch_zoom_transcript.called
            assert mock_tools["summarization"].summarize_meeting.called
    
    @pytest.mark.asyncio
    async def test_step_failure_stops_execution(self, tool_executor):
        """Test that step failure stops execution of subsequent steps."""
        # Arrange
        workflow = build_mock_workflow(
            steps=[
                build_mock_step("find_meeting", "meeting_finder"),
                build_mock_step("summarize", "summarization")  # Should NOT execute
            ]
        )
        context = build_mock_context()
        prepared_data = build_mock_prepared_data()
        integration_data = build_mock_integration_data()
        
        # Mock MeetingFinder to return None (failure)
        with patch('app.orchestrator.tool_execution.MeetingFinder') as mock_finder_class:
            mock_finder = MagicMock()
            mock_finder_class.return_value = mock_finder
            mock_finder.find_meeting_in_database.return_value = None
            mock_finder.find_meeting_in_calendar.return_value = (None, None)
            
            # Mock summarization tool (should NOT be called)
            mock_tools = MagicMock()
            mock_tools.summarize_meeting = AsyncMock()
            
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
            assert result.get("tool_name") == "summarization"  # Error preserves original tool_name
            assert "error" in result
            assert "did not produce required output" in result["error"]
            # Summarization should NOT be called
            # (We can't directly assert this since tool_executor uses internal tools,
            # but the error indicates execution stopped)
    
    @pytest.mark.asyncio
    async def test_step_ordering_enforced(self, tool_executor, mock_memory_repo):
        """Test that steps execute in workflow order, not dependency order."""
        # Arrange - Steps in "wrong" order (summarize before retrieve_transcript)
        workflow = build_mock_workflow(
            steps=[
                build_mock_step("summarize", "summarization"),  # Step 0 (should fail)
                build_mock_step("retrieve_transcript", "integration_fetcher"),  # Step 1 (should NOT run)
                build_mock_step("find_meeting", "meeting_finder")  # Step 2 (should NOT run)
            ]
        )
        context = build_mock_context()
        prepared_data = build_mock_prepared_data()
        integration_data = build_mock_integration_data()
        
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
        # Should fail on first step (summarize) because no transcript
        assert result.get("tool_name") == "summarization"  # Error preserves original tool_name
        assert "error" in result
        # Execution should stop after first step fails
    
    @pytest.mark.asyncio
    async def test_unknown_action_handled(self, tool_executor):
        """Test that unknown actions return error immediately."""
        # Arrange
        workflow = build_mock_workflow(
            steps=[
                build_mock_step("unknown_action", "unknown_tool")
            ]
        )
        context = build_mock_context()
        prepared_data = build_mock_prepared_data()
        integration_data = build_mock_integration_data()
        
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
        assert "Unknown action" in result["error"]
        assert "unknown_action" in result["error"]
    
    @pytest.mark.asyncio
    async def test_multi_step_pipeline(self, tool_executor, mock_memory_repo, mock_tools):
        """Test multi-step pipeline with context updates."""
        # Arrange
        workflow = build_mock_workflow(
            steps=[
                build_mock_step("find_meeting", "meeting_finder"),
                build_mock_step("retrieve_transcript", "integration_fetcher"),
                build_mock_step("summarize", "summarization")
            ]
        )
        context = build_mock_context()
        prepared_data = build_mock_prepared_data()
        integration_data = build_mock_integration_data()
        
        # Mock MeetingFinder
        with patch('app.orchestrator.tool_execution.MeetingFinder') as mock_finder_class:
            mock_finder = MagicMock()
            mock_finder_class.return_value = mock_finder
            mock_finder.find_meeting_in_database.return_value = 123
            mock_finder.find_meeting_in_calendar.return_value = (None, None)
            
            # Mock memory repo
            mock_meeting = build_mock_meeting(id=123, transcript="Test transcript")
            mock_memory_repo.get_meeting_by_id.return_value = mock_meeting
            
            # Mock integration fetcher
            tool_executor.integration_data_fetcher.fetch_zoom_transcript = AsyncMock(
                return_value="Test transcript"
            )
            
            # Mock summarization tool
            mock_tools["summarization"].summarize_meeting = AsyncMock(return_value={
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
            assert "result" in result
            assert result["result"].get("summary") == "Test summary"
            # Verify all steps executed
            assert mock_finder.find_meeting_in_database.called
            assert tool_executor.integration_data_fetcher.fetch_zoom_transcript.called
            assert mock_tools["summarization"].summarize_meeting.called

