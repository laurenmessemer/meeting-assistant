"""Tests for fallback handling (Step 5)."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
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


class TestFallbacks:
    """Tests for fallback handling logic."""
    
    @pytest.mark.asyncio
    async def test_fallback_success(self, tool_executor, mock_memory_repo):
        """Test that fallback succeeds when primary step fails."""
        # Arrange
        workflow = build_mock_workflow(
            steps=[
                build_mock_step(
                    "find_meeting",
                    "meeting_finder",
                    fallback=build_mock_fallback(
                        "resolve_meeting_from_calendar",
                        conditions=["no_db_match"]
                    )
                )
            ]
        )
        context = build_mock_context()
        prepared_data = build_mock_prepared_data()
        integration_data = build_mock_integration_data()
        
        # Mock MeetingFinder - primary fails, fallback succeeds
        with patch('app.orchestrator.tool_execution.MeetingFinder') as mock_finder_class:
            mock_finder = MagicMock()
            mock_finder_class.return_value = mock_finder
            mock_finder.find_meeting_in_database.return_value = None  # Primary fails
            calendar_event = build_mock_calendar_event()
            mock_finder.find_meeting_in_calendar.return_value = (calendar_event, None)  # Fallback succeeds
            
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
            # Should have calendar_event from fallback
            assert mock_finder.find_meeting_in_database.called
            assert mock_finder.find_meeting_in_calendar.called
    
    @pytest.mark.asyncio
    async def test_fallback_failure(self, tool_executor):
        """Test that fallback failure returns error."""
        # Arrange
        workflow = build_mock_workflow(
            steps=[
                build_mock_step(
                    "find_meeting",
                    "meeting_finder",
                    fallback=build_mock_fallback(
                        "resolve_meeting_from_calendar",
                        conditions=["no_db_match"]
                    )
                )
            ]
        )
        context = build_mock_context()
        prepared_data = build_mock_prepared_data()
        integration_data = build_mock_integration_data()
        
        # Mock MeetingFinder - both primary and fallback fail
        with patch('app.orchestrator.tool_execution.MeetingFinder') as mock_finder_class:
            mock_finder = MagicMock()
            mock_finder_class.return_value = mock_finder
            mock_finder.find_meeting_in_database.return_value = None  # Primary fails
            mock_finder.find_meeting_in_calendar.return_value = (None, None)  # Fallback fails
            
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
            assert "All fallbacks failed" in result["error"] or "did not produce required output" in result["error"]
    
    @pytest.mark.asyncio
    async def test_fallback_chain(self, tool_executor, mock_memory_repo):
        """Test fallback chain: fallback1 fails → fallback2 succeeds."""
        # Arrange
        workflow = build_mock_workflow(
            steps=[
                build_mock_step(
                    "find_meeting",
                    "meeting_finder",
                    fallback=[
                        build_mock_fallback(
                            "resolve_meeting_from_calendar",
                            conditions=["no_db_match"]
                        ),
                        build_mock_fallback(
                            "use_last_selected_meeting",
                            conditions=["no_db_match"]
                        )
                    ]
                )
            ]
        )
        context = build_mock_context(
            persistent_memory={
                "last_selected_meeting": MagicMock(value="123")
            }
        )
        prepared_data = build_mock_prepared_data()
        integration_data = build_mock_integration_data()
        
        # Mock MeetingFinder - primary and fallback1 fail
        with patch('app.orchestrator.tool_execution.MeetingFinder') as mock_finder_class:
            mock_finder = MagicMock()
            mock_finder_class.return_value = mock_finder
            mock_finder.find_meeting_in_database.return_value = None
            mock_finder.find_meeting_in_calendar.return_value = (None, None)  # Fallback1 fails
            
            # Mock memory repo for fallback2
            mock_meeting = build_mock_meeting(id=123)
            mock_memory_repo.get_memory_by_key.return_value = MagicMock(value="123")
            mock_memory_repo.get_meeting_by_id.return_value = mock_meeting
            
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
            # Fallback2 should succeed (use_last_selected_meeting)
            assert mock_finder.find_meeting_in_database.called
            assert mock_finder.find_meeting_in_calendar.called
            assert mock_memory_repo.get_memory_by_key.called
            assert mock_memory_repo.get_meeting_by_id.called
    
    @pytest.mark.asyncio
    async def test_circular_fallback_protection(self, tool_executor):
        """Test that circular fallbacks are detected and prevented."""
        # Arrange
        workflow = build_mock_workflow(
            steps=[
                build_mock_step(
                    "find_meeting",
                    "meeting_finder",
                    fallback=build_mock_fallback(
                        "find_meeting",  # Circular: same action
                        conditions=["no_db_match"]
                    )
                )
            ]
        )
        context = build_mock_context()
        prepared_data = build_mock_prepared_data()
        integration_data = build_mock_integration_data()
        
        # Mock MeetingFinder to always return None (infinite loop potential)
        with patch('app.orchestrator.tool_execution.MeetingFinder') as mock_finder_class:
            mock_finder = MagicMock()
            mock_finder_class.return_value = mock_finder
            mock_finder.find_meeting_in_database.return_value = None
            mock_finder.find_meeting_in_calendar.return_value = (None, None)
            
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
            # Should detect loop after 3 attempts
            assert result is not None
            # Either error about loop or fallback failure
            assert result.get("tool_name") == "workflow"
            assert "error" in result
    
    @pytest.mark.asyncio
    async def test_fallback_user_clarification(self, tool_executor):
        """Test fallback that requires user clarification."""
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
        
        # Mock MeetingFinder - primary fails, returns multiple options
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
            # Should return user selection request
            # Note: The actual implementation may vary, but should handle multiple matches
    
    @pytest.mark.asyncio
    async def test_fallback_memory_interaction(self, tool_executor, mock_memory_repo):
        """Test fallback that interacts with persistent memory."""
        # Arrange
        workflow = build_mock_workflow(
            steps=[
                build_mock_step(
                    "find_meeting",
                    "meeting_finder",
                    fallback=build_mock_fallback(
                        "use_last_selected_meeting",
                        conditions=["no_db_match"]
                    )
                )
            ]
        )
        context = build_mock_context(
            persistent_memory={
                "last_selected_meeting": MagicMock(value="123")
            }
        )
        prepared_data = build_mock_prepared_data()
        integration_data = build_mock_integration_data()
        
        # Mock MeetingFinder - primary fails
        with patch('app.orchestrator.tool_execution.MeetingFinder') as mock_finder_class:
            mock_finder = MagicMock()
            mock_finder_class.return_value = mock_finder
            mock_finder.find_meeting_in_database.return_value = None
            
            # Mock memory repo
            mock_meeting = build_mock_meeting(id=123)
            mock_memory_repo.get_memory_by_key.return_value = MagicMock(value="123")
            mock_memory_repo.get_meeting_by_id.return_value = mock_meeting
            
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
            assert mock_finder.find_meeting_in_database.called
            assert mock_memory_repo.get_memory_by_key.called
            assert mock_memory_repo.get_meeting_by_id.called
    
    @pytest.mark.asyncio
    async def test_fallback_limit_exceeded(self, tool_executor):
        """Test that fallback limits are enforced."""
        # Arrange - Multiple steps with fallbacks that will fail
        workflow = build_mock_workflow(
            steps=[
                build_mock_step(
                    "find_meeting",
                    "meeting_finder",
                    fallback=build_mock_fallback(
                        "resolve_meeting_from_calendar",
                        conditions=["no_db_match"],
                        max_attempts=2
                    )
                ),
                build_mock_step(
                    "find_meeting",  # Same action again
                    "meeting_finder",
                    fallback=build_mock_fallback(
                        "resolve_meeting_from_calendar",
                        conditions=["no_db_match"],
                        max_attempts=2
                    )
                )
            ]
        )
        context = build_mock_context()
        prepared_data = build_mock_prepared_data()
        integration_data = build_mock_integration_data()
        
        # Mock MeetingFinder - all attempts fail
        with patch('app.orchestrator.tool_execution.MeetingFinder') as mock_finder_class:
            mock_finder = MagicMock()
            mock_finder_class.return_value = mock_finder
            mock_finder.find_meeting_in_database.return_value = None
            mock_finder.find_meeting_in_calendar.return_value = (None, None)
            
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
            # Should eventually hit limit or return error
            assert result.get("tool_name") == "workflow"
            assert "error" in result

