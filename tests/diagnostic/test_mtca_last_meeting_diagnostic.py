"""Diagnostic test for MTCA last meeting summarization failure.

This test reproduces the scenario where:
- User asks: "Summarize my last meeting with MTCA"
- Calendar has matching events
- Database has meeting rows but transcripts are missing
- Expected: Agent selects most recent calendar event and either falls back 
  to summarizing metadata OR asks user to select a meeting
"""

import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime, timezone, timedelta
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.orchestrator.agent import AgentOrchestrator
from app.memory.repo import MemoryRepository
from app.memory.models import Meeting, Client
from sqlalchemy.orm import Session


@pytest.fixture
def mock_db():
    """Create a mock database session."""
    return MagicMock(spec=Session)


@pytest.fixture
def mock_memory_repo():
    """Create a mock memory repository with MTCA meetings without transcripts."""
    repo = MagicMock(spec=MemoryRepository)
    
    # Create mock MTCA client
    mtca_client = MagicMock(spec=Client)
    mtca_client.id = 1
    mtca_client.name = "MTCA"
    
    # Create mock meetings for MTCA (past meetings, no transcripts)
    now = datetime.now(timezone.utc)
    past_date_1 = now - timedelta(days=5)
    past_date_2 = now - timedelta(days=10)
    
    meeting_1 = MagicMock(spec=Meeting)
    meeting_1.id = 1
    meeting_1.title = "MTCA Strategy Meeting"
    meeting_1.scheduled_time = past_date_1.replace(tzinfo=None)
    meeting_1.transcript = None  # No transcript
    meeting_1.recording_url = None  # No recording
    meeting_1.client_id = 1
    meeting_1.client = mtca_client
    
    meeting_2 = MagicMock(spec=Meeting)
    meeting_2.id = 2
    meeting_2.title = "MTCA Quarterly Review"
    meeting_2.scheduled_time = past_date_2.replace(tzinfo=None)
    meeting_2.transcript = None  # No transcript
    meeting_2.recording_url = None  # No recording
    meeting_2.client_id = 1
    meeting_2.client = mtca_client
    
    # Mock repository methods
    repo.search_clients_by_name.return_value = [mtca_client]
    repo.get_meetings_by_client.return_value = [meeting_1, meeting_2]
    repo.get_meeting_by_id.return_value = meeting_1
    repo.get_client_by_id.return_value = mtca_client
    
    return repo


@pytest.fixture
def mock_calendar_events():
    """Create mock calendar events for MTCA."""
    now = datetime.now(timezone.utc)
    event_date_1 = now - timedelta(days=3)  # More recent than DB meetings
    
    events = [
        {
            'id': 'cal_event_1',
            'summary': 'MTCA Weekly Sync',
            'start': {'dateTime': event_date_1.isoformat()},
            'end': {'dateTime': (event_date_1 + timedelta(hours=1)).isoformat()},
            'description': '',
            'location': '',
            'attendees': [
                {'email': 'user@example.com', 'displayName': 'User'},
                {'email': 'mtca@example.com', 'displayName': 'MTCA Contact'}
            ]
        }
    ]
    
    return events


@pytest.mark.asyncio
async def test_mtca_last_meeting_diagnostic(mock_db, mock_memory_repo, mock_calendar_events):
    """
    Diagnostic test: "Summarize my last meeting with MTCA"
    
    This test should reveal:
    1. Whether past meetings without transcripts are filtered out
    2. Which calendar event is selected as "last"
    3. Why calendar_event is not converted to meeting_id
    4. What condition triggers "Cannot retrieve transcript: no calendar_event or meeting_id"
    """
    
    # Mock Google Calendar client
    with patch('app.integrations.google_calendar_client.search_calendar_events_by_keyword') as mock_search:
        # Return mock calendar events (most recent one)
        mock_search.return_value = mock_calendar_events
        
        # Mock LLM responses
        with patch('app.llm.gemini_client.GeminiClient') as mock_llm_class:
            mock_llm = MagicMock()
            mock_llm_class.return_value = mock_llm
            
            # Mock intent recognition
            mock_llm.llm_chat.return_value = {
                "intent": "summarize_meeting",
                "client_name": "MTCA",
                "confidence": 0.9
            }
            
            # Create orchestrator
            orchestrator = AgentOrchestrator(mock_db, mock_memory_repo, mock_llm)
            
            # Run the diagnostic test
            print("\n" + "="*80)
            print("DIAGNOSTIC TEST: Summarize my last meeting with MTCA")
            print("="*80)
            print("\nTest Scenario:")
            print("  - User asks: 'Summarize my last meeting with MTCA'")
            print("  - Database has 2 past MTCA meetings (no transcripts)")
            print("  - Calendar has 1 more recent MTCA event")
            print("  - Expected: System should select calendar event or ask for selection")
            print("\n" + "-"*80)
            
            try:
                result = await orchestrator.process_message(
                    message="Summarize my last meeting with MTCA",
                    user_id=1,
                    debug=True
                )
                
                print("\n" + "-"*80)
                print("RESULT:")
                print(f"  Response: {result.get('response', 'N/A')[:200]}...")
                print(f"  Tool used: {result.get('tool_used', 'N/A')}")
                print(f"  Meeting options: {result.get('meeting_options', 'N/A')}")
                print(f"  Error: {result.get('metadata', {}).get('error', 'None')}")
                
            except Exception as e:
                print(f"\n❌ EXCEPTION: {type(e).__name__}: {str(e)}")
                import traceback
                print("\nTraceback:")
                print(traceback.format_exc())
            
            print("\n" + "="*80)
            print("END DIAGNOSTIC TEST")
            print("="*80 + "\n")


if __name__ == "__main__":
    # Run the test directly
    asyncio.run(test_mtca_last_meeting_diagnostic(
        MagicMock(spec=Session),
        MagicMock(spec=MemoryRepository),
        []
    ))

