"""Shared pytest fixtures and utilities for all tests."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.orm import Session
from typing import Dict, Any, Optional, List

from app.orchestrator.agent import AgentOrchestrator
from app.orchestrator.tool_execution import ToolExecutor
from app.memory.repo import MemoryRepository
from app.orchestrator.meeting_finder import MeetingFinder
from app.orchestrator.integration_data_fetching import IntegrationDataFetcher
from app.tools.summarization import SummarizationTool
from app.tools.followup import FollowUpTool
from app.tools.meeting_brief import MeetingBriefTool
from app.llm.gemini_client import GeminiClient


@pytest.fixture
def mock_db():
    """Mock database session."""
    return MagicMock(spec=Session)


@pytest.fixture
def mock_llm():
    """Mock LLM client."""
    llm = MagicMock(spec=GeminiClient)
    llm.llm_chat = MagicMock()  # llm_chat is not async
    return llm


@pytest.fixture
def mock_memory_repo():
    """Mock memory repository."""
    repo = MagicMock(spec=MemoryRepository)
    repo.get_meeting_by_id = MagicMock(return_value=None)
    repo.get_client_by_id = MagicMock(return_value=None)
    repo.get_memory_by_key = MagicMock(return_value=None)
    repo.get_relevant_memories = MagicMock(return_value=[])
    repo.get_client_context = MagicMock(return_value={})
    repo.create_meeting = MagicMock()
    repo.update_meeting = MagicMock()
    repo.save_decisions = MagicMock()
    repo.save_interaction_memory = MagicMock()
    repo.save_memory_by_key = MagicMock()
    repo.create_or_update_memory_entry = MagicMock()
    repo.get_decisions_by_meeting_id = MagicMock(return_value=[])
    repo.get_meetings_by_client = MagicMock(return_value=[])
    repo.search_clients_by_name = MagicMock(return_value=[])
    repo.get_client_by_exact_name = MagicMock(return_value=None)
    return repo


@pytest.fixture
def mock_meeting_finder():
    """Mock meeting finder."""
    finder = MagicMock(spec=MeetingFinder)
    finder.find_meeting_in_database = MagicMock(return_value=None)
    finder.find_meeting_in_calendar = MagicMock(return_value=(None, None))
    return finder


@pytest.fixture
def mock_integration_fetcher():
    """Mock integration data fetcher."""
    fetcher = MagicMock(spec=IntegrationDataFetcher)
    fetcher.fetch_zoom_transcript = AsyncMock(return_value=None)
    fetcher.process_calendar_event_for_summarization = AsyncMock(return_value={})
    fetcher.prepare_integration_data = AsyncMock(return_value={})
    return fetcher


@pytest.fixture
def mock_tools():
    """Mock all tools."""
    return {
        "summarization": MagicMock(spec=SummarizationTool),
        "followup": MagicMock(spec=FollowUpTool),
        "meeting_brief": MagicMock(spec=MeetingBriefTool)
    }


@pytest.fixture
def tool_executor(mock_db, mock_memory_repo, mock_tools, mock_integration_fetcher):
    """Create ToolExecutor with mocked dependencies."""
    return ToolExecutor(
        mock_db,
        mock_memory_repo,
        mock_tools["summarization"],
        mock_tools["meeting_brief"],
        mock_tools["followup"],
        mock_integration_fetcher
    )


@pytest.fixture
def agent_orchestrator(mock_db, mock_llm):
    """Create AgentOrchestrator with mocked dependencies."""
    with patch('app.orchestrator.agent.GeminiClient', return_value=mock_llm):
        return AgentOrchestrator(mock_db)

