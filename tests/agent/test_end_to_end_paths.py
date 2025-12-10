"""End-to-end integration tests for full orchestrator pipeline."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from tests.integrations.test_integration_mocks import (
    build_mock_workflow,
    build_mock_step,
    build_mock_fallback,
    build_mock_context,
    build_mock_prepared_data,
    build_mock_integration_data,
    build_mock_meeting,
    build_mock_calendar_event
)


class TestEndToEndPaths:
    """End-to-end integration tests for complete pipeline scenarios."""
    
    @pytest.mark.asyncio
    async def test_integration_missing_meeting_fallback_chain(
        self, tool_executor, mock_memory_repo, mock_tools
    ):
        """Scenario 1: Missing meeting → fallback calendar search → summarize → follow-up."""
        # Arrange
        workflow = build_mock_workflow(
            required_data=["meeting_id"],
            steps=[
                build_mock_step(
                    "find_meeting",
                    "meeting_finder",
                    fallback=build_mock_fallback(
                        "resolve_meeting_from_calendar",
                        conditions=["no_db_match"]
                    )
                ),
                build_mock_step("retrieve_transcript", "integration_fetcher"),
                build_mock_step("summarize", "summarization"),
                build_mock_step("generate_followup", "followup")
            ]
        )
        context = build_mock_context()
        prepared_data = build_mock_prepared_data()
        integration_data = build_mock_integration_data()
        
        # Mock MeetingFinder - primary fails, fallback succeeds
        with patch('app.orchestrator.tool_execution.MeetingFinder') as mock_finder_class:
            mock_finder = MagicMock()
            mock_finder_class.return_value = mock_finder
            mock_finder.find_meeting_in_database.return_value = None
            calendar_event = build_mock_calendar_event()
            mock_finder.find_meeting_in_calendar.return_value = (calendar_event, None)
            
            # Mock integration fetcher
            tool_executor.integration_data_fetcher.fetch_zoom_transcript = AsyncMock(
                return_value="Test transcript"
            )
            
            # Mock summarization tool
            mock_tools["summarization"].summarize_meeting = AsyncMock(return_value={
                "tool_name": "summarization",
                "result": {"summary": "Test summary"}
            })
            
            # Mock follow-up tool
            mock_tools["followup"].generate_followup = AsyncMock(return_value={
                "tool_name": "followup",
                "result": {"email": "Test email"}
            })
            
            # Mock memory repo
            mock_meeting = build_mock_meeting(id=123, transcript="Test transcript")
            mock_memory_repo.get_meeting_by_id.return_value = mock_meeting
            
            # Act
            result = await tool_executor.execute(
                "summarization",
                "Summarize my meeting with MTCA on October 29th",
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
            # Verify all steps executed
            assert mock_finder.find_meeting_in_database.called
            assert mock_finder.find_meeting_in_calendar.called
            assert tool_executor.integration_data_fetcher.fetch_zoom_transcript.called
            assert mock_tools["summarization"].summarize_meeting.called
            assert mock_tools["followup"].generate_followup.called
    
    @pytest.mark.asyncio
    async def test_integration_invalid_summary_fallback(
        self, tool_executor, mock_memory_repo, mock_tools
    ):
        """Scenario 2: Invalid summary → fallback re-summarization → follow-up."""
        # Arrange
        workflow = build_mock_workflow(
            steps=[
                build_mock_step("find_meeting", "meeting_finder"),
                build_mock_step(
                    "summarize",
                    "summarization",
                    fallback=build_mock_fallback(
                        "force_summarization",
                        conditions=["tool_failure"]
                    )
                ),
                build_mock_step("generate_followup", "followup")
            ]
        )
        context = build_mock_context()
        prepared_data = build_mock_prepared_data()
        integration_data = build_mock_integration_data(
            meeting_id=123,
            structured_data={"transcript": "Valid transcript"}
        )
        
        # Mock MeetingFinder
        with patch('app.orchestrator.tool_execution.MeetingFinder') as mock_finder_class:
            mock_finder = MagicMock()
            mock_finder_class.return_value = mock_finder
            mock_finder.find_meeting_in_database.return_value = 123
            
            # Mock memory repo
            mock_meeting = build_mock_meeting(id=123, transcript="Valid transcript")
            mock_memory_repo.get_meeting_by_id.return_value = mock_meeting
            
            # Mock summarization - first call fails, fallback succeeds
            call_count = [0]
            def summarize_side_effect(*args, **kwargs):
                call_count[0] += 1
                if call_count[0] == 1:
                    return {"tool_name": "summarization", "error": "Summary generation failed"}
                else:
                    return {"tool_name": "summarization", "result": {"summary": "New summary"}}
            
            mock_tools["summarization"].summarize_meeting = AsyncMock(side_effect=summarize_side_effect)
            
            # Mock follow-up tool
            mock_tools["followup"].generate_followup = AsyncMock(return_value={
                "tool_name": "followup",
                "result": {"email": "Test email"}
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
            # Summarization should be called at least once (fallback may retry)
            assert mock_tools["summarization"].summarize_meeting.called
    
    @pytest.mark.asyncio
    async def test_integration_missing_transcript_fallback(
        self, tool_executor, mock_memory_repo, mock_tools
    ):
        """Scenario 3: Transcript missing → fallback transcript fetch → summarization."""
        # Arrange
        workflow = build_mock_workflow(
            steps=[
                build_mock_step("find_meeting", "meeting_finder"),
                build_mock_step(
                    "retrieve_transcript",
                    "integration_fetcher",
                    fallback=build_mock_fallback(
                        "skip_step",
                        conditions=["no_transcript"]
                    )
                ),
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
            
            # Mock memory repo
            mock_meeting = build_mock_meeting(id=123, transcript=None)
            mock_memory_repo.get_meeting_by_id.return_value = mock_meeting
            
            # Mock integration fetcher - transcript fetch fails
            tool_executor.integration_data_fetcher.fetch_zoom_transcript = AsyncMock(
                return_value=None
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
            # Transcript fetch should be attempted
            assert tool_executor.integration_data_fetcher.fetch_zoom_transcript.called
    
    @pytest.mark.asyncio
    async def test_integration_ambiguous_meeting_user_selection(self, tool_executor):
        """Scenario 4: Ambiguous meeting → fallback → user selection required."""
        # Arrange
        workflow = build_mock_workflow(
            steps=[
                build_mock_step(
                    "find_meeting",
                    "meeting_finder",
                    fallback=build_mock_fallback(
                        "ask_user_for_meeting",
                        conditions=["no_db_match"],
                        message_to_user="Which meeting did you mean?"
                    )
                )
            ]
        )
        context = build_mock_context()
        prepared_data = build_mock_prepared_data()
        integration_data = build_mock_integration_data()
        
        # Mock MeetingFinder - returns multiple matches
        with patch('app.orchestrator.tool_execution.MeetingFinder') as mock_finder_class:
            mock_finder = MagicMock()
            mock_finder_class.return_value = mock_finder
            mock_finder.find_meeting_in_database.return_value = None
            meeting_options = [MagicMock(), MagicMock()]
            mock_finder.find_meeting_in_calendar.return_value = (None, meeting_options)
            
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
            # Should handle multiple matches appropriately
            assert mock_finder.find_meeting_in_database.called
            assert mock_finder.find_meeting_in_calendar.called
    
    @pytest.mark.asyncio
    async def test_integration_unknown_step_handled(self, tool_executor):
        """Scenario 5: Planner hallucinated unknown step → safe error."""
        # Arrange
        workflow = build_mock_workflow(
            steps=[
                build_mock_step("hallucinated_action", "unknown_tool")
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
        assert "hallucinated_action" in result["error"]

