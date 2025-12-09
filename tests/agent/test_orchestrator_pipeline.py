"""Tests for full orchestrator pipeline with mocked integrations."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.orm import Session
from app.orchestrator.agent import AgentOrchestrator


class TestOrchestratorPipeline:
    """Tests for full orchestrator pipeline with mocked integrations."""
    
    @pytest.fixture
    def mock_db(self):
        """Create a mocked database session."""
        return MagicMock(spec=Session)
    
    @pytest.fixture
    def mock_llm(self):
        """Create a mocked LLM client."""
        llm = MagicMock()
        llm.llm_chat = AsyncMock()
        return llm
    
    @pytest.fixture
    def fake_zoom_transcript(self):
        """Fake Zoom transcript for testing."""
        return """
        [00:00:00] Speaker 1: Welcome everyone to today's meeting.
        [00:00:15] Speaker 2: Thank you for joining. Let's discuss the project timeline.
        [00:05:30] Speaker 1: We need to complete Phase 1 by next week.
        [00:10:45] Speaker 2: Agreed. We'll allocate resources accordingly.
        """
    
    @pytest.fixture
    def fake_calendar_event(self):
        """Fake calendar event for testing."""
        return {
            'id': 'test_event_123',
            'summary': 'Client Meeting - Project Discussion',
            'start': {
                'dateTime': '2024-05-01T10:00:00Z'
            },
            'attendees': [
                {'displayName': 'John Doe', 'email': 'john@example.com'},
                {'displayName': 'Jane Smith', 'email': 'jane@example.com'}
            ]
        }
    
    @pytest.fixture
    def fake_hubspot_data(self):
        """Fake HubSpot data for testing."""
        return {
            'contact': {
                'id': '12345',
                'name': 'Acme Corp',
                'email': 'contact@acme.com'
            },
            'deals': [
                {'id': 'deal1', 'name': 'Project X', 'amount': 50000}
            ]
        }
    
    @pytest.fixture
    def fake_memory(self):
        """Fake memory entries for testing."""
        return [
            {
                'key': 'previous_meeting_summary',
                'value': 'Last meeting discussed project timeline',
                'extra_data': {'meeting_id': 1}
            }
        ]
    
    @pytest.mark.asyncio
    async def test_summarization_pipeline(
        self,
        mock_db,
        fake_zoom_transcript,
        fake_calendar_event,
        fake_hubspot_data,
        fake_memory
    ):
        """Test full summarization pipeline with mocked integrations."""
        # Create a single mock LLM that will be used by all components
        mock_llm = MagicMock()
        mock_llm.llm_chat = MagicMock()
        
        # Set up side_effect to return different values for different calls
        call_count = [0]
        def llm_chat_side_effect(*args, **kwargs):
            count = call_count[0]
            call_count[0] += 1
            # Intent recognition (first call)
            if count == 0:
                return {
                    "intent": "summarization",
                    "confidence": 0.95,
                    "extracted_info": {"meeting_type": "last"}
                }
            # Workflow planning (second call)
            elif count == 1:
                return {"steps": ["Find meeting", "Retrieve transcript", "Summarize"]}
            # Summarization tool (third call)
            elif count == 2:
                return {
                    "summary": "Meeting discussed project timeline and resource allocation.",
                    "decisions": [{"description": "Complete Phase 1 by next week"}],
                    "action_items": []
                }
            # Output synthesis (fourth call)
            elif count == 3:
                return "Here's a summary of your meeting: The team discussed the project timeline..."
            else:
                return "Default response"
        
        mock_llm.llm_chat.side_effect = llm_chat_side_effect
        
        # Patch GeminiClient in all the places it's used
        with patch('app.orchestrator.agent.GeminiClient', return_value=mock_llm), \
             patch('app.orchestrator.intent_recognition.GeminiClient', return_value=mock_llm), \
             patch('app.orchestrator.workflow_planning.GeminiClient', return_value=mock_llm), \
             patch('app.orchestrator.output_synthesis.GeminiClient', return_value=mock_llm), \
             patch('app.tools.summarization.GeminiClient', return_value=mock_llm), \
             patch('app.orchestrator.agent.MemoryRepository') as mock_memory_class, \
             patch('app.orchestrator.agent.IntegrationDataFetcher') as mock_fetcher_class:
            
            mock_memory = MagicMock()
            mock_memory_class.return_value = mock_memory
            mock_memory.get_relevant_memories.return_value = []
            mock_memory.get_client_context.return_value = fake_hubspot_data
            mock_memory.get_meeting_by_id.return_value = None
            mock_memory.create_meeting.return_value = MagicMock(id=1)
            mock_memory.save_decisions = MagicMock()
            mock_memory.update_meeting = MagicMock()
            mock_memory.save_interaction_memory = MagicMock()
            
            mock_fetcher = MagicMock()
            mock_fetcher_class.return_value = mock_fetcher
            mock_fetcher.process_calendar_event_for_summarization = AsyncMock(return_value={
                "meeting_title": "Client Meeting",
                "meeting_date": "May 01, 2024 at 10:00 AM",
                "recording_date": "May 01, 2024 at 10:00 AM",
                "attendees": "John Doe, Jane Smith",
                "transcript": fake_zoom_transcript,
                "has_transcript": True,
                "meeting_id": 1
            })
            
            orchestrator = AgentOrchestrator(mock_db)
            result = await orchestrator.process_message(
                message="Summarize my last meeting",
                user_id=1,
                client_id=1
            )
            
            # Assertions - check that pipeline completed successfully
            assert "response" in result
            # Check intent (more stable than tool_used)
            assert result["metadata"]["intent"] == "summarization"
            # Verify a response was generated
            assert len(result["response"]) > 0
    
    @pytest.mark.asyncio
    async def test_meeting_brief_pipeline(
        self,
        mock_db,
        fake_calendar_event,
        fake_hubspot_data,
        fake_memory
    ):
        """Test full meeting brief pipeline with mocked integrations."""
        # Create a single mock LLM
        mock_llm = MagicMock()
        mock_llm.llm_chat = MagicMock()
        
        call_count = [0]
        def llm_chat_side_effect(*args, **kwargs):
            count = call_count[0]
            call_count[0] += 1
            if count == 0:
                return {"intent": "meeting_brief", "confidence": 0.92, "extracted_info": {}}
            elif count == 1:
                return {"steps": ["Find next meeting", "Get client info", "Generate brief"]}
            elif count == 2:
                return {
                    "brief": "Upcoming meeting with Acme Corp. Previous discussion covered project timeline.",
                    "key_points": ["Project status", "Resource allocation"]
                }
            elif count == 3:
                return "Here's your meeting brief for the upcoming meeting..."
            else:
                return "Default response"
        
        mock_llm.llm_chat.side_effect = llm_chat_side_effect
        
        with patch('app.orchestrator.agent.GeminiClient', return_value=mock_llm), \
             patch('app.orchestrator.intent_recognition.GeminiClient', return_value=mock_llm), \
             patch('app.orchestrator.workflow_planning.GeminiClient', return_value=mock_llm), \
             patch('app.orchestrator.output_synthesis.GeminiClient', return_value=mock_llm), \
             patch('app.tools.meeting_brief.GeminiClient', return_value=mock_llm), \
             patch('app.orchestrator.agent.MemoryRepository') as mock_memory_class, \
             patch('app.orchestrator.agent.IntegrationDataFetcher') as mock_fetcher_class:
            
            mock_memory = MagicMock()
            mock_memory_class.return_value = mock_memory
            mock_memory.get_relevant_memories.return_value = []
            mock_memory.get_client_context.return_value = fake_hubspot_data
            mock_memory.get_client_by_id.return_value = MagicMock(name="Acme Corp")
            mock_memory.get_meetings_by_client.return_value = []
            mock_memory.save_interaction_memory = MagicMock()
            
            mock_fetcher = MagicMock()
            mock_fetcher_class.return_value = mock_fetcher
            mock_fetcher.get_calendar_event_details.return_value = {
                "meeting_title": "Client Meeting",
                "meeting_date": "May 01, 2024 at 10:00 AM",
                "attendees": "John Doe, Jane Smith"
            }
            
            orchestrator = AgentOrchestrator(mock_db)
            result = await orchestrator.process_message(
                message="Prepare me for my next meeting",
                user_id=1,
                client_id=1
            )
            
            assert "response" in result
            assert result["metadata"]["intent"] == "meeting_brief"
            assert len(result["response"]) > 0
    
    @pytest.mark.asyncio
    async def test_followup_pipeline(
        self,
        mock_db,
        fake_hubspot_data
    ):
        """Test full followup pipeline with mocked integrations."""
        # Create a single mock LLM
        mock_llm = MagicMock()
        mock_llm.llm_chat = MagicMock()
        
        call_count = [0]
        def llm_chat_side_effect(*args, **kwargs):
            count = call_count[0]
            call_count[0] += 1
            if count == 0:
                return {"intent": "followup", "confidence": 0.88, "extracted_info": {}}
            elif count == 1:
                return {"steps": ["Find meeting", "Get summary", "Generate followup"]}
            elif count == 2:
                return {
                    "followup_email": "Subject: Follow-up on Project Discussion\n\nDear Team...",
                    "action_items": ["Complete Phase 1 by next week"]
                }
            elif count == 3:
                return "Here's your follow-up email..."
            else:
                return "Default response"
        
        mock_llm.llm_chat.side_effect = llm_chat_side_effect
        
        with patch('app.orchestrator.agent.GeminiClient', return_value=mock_llm), \
             patch('app.orchestrator.intent_recognition.GeminiClient', return_value=mock_llm), \
             patch('app.orchestrator.workflow_planning.GeminiClient', return_value=mock_llm), \
             patch('app.orchestrator.output_synthesis.GeminiClient', return_value=mock_llm), \
             patch('app.tools.followup.GeminiClient', return_value=mock_llm), \
             patch('app.orchestrator.agent.MemoryRepository') as mock_memory_class:
            
            mock_memory = MagicMock()
            mock_memory_class.return_value = mock_memory
            mock_memory.get_relevant_memories.return_value = []
            mock_memory.get_client_context.return_value = fake_hubspot_data
            mock_memory.get_meetings_by_client.return_value = [
                MagicMock(
                    id=1,
                    summary="Meeting discussed project timeline",
                    transcript="Transcript text",
                    title="Client Meeting",
                    status="completed",
                    client_id=1
                )
            ]
            mock_memory.get_client_by_id.return_value = MagicMock(name="Acme Corp")
            mock_memory.get_decisions_by_meeting_id.return_value = []
            mock_memory.save_interaction_memory = MagicMock()
            
            orchestrator = AgentOrchestrator(mock_db)
            result = await orchestrator.process_message(
                message="Draft a follow-up email",
                user_id=1,
                client_id=1
            )
            
            assert "response" in result
            assert result["metadata"]["intent"] == "followup"
            assert len(result["response"]) > 0
    
    @pytest.mark.asyncio
    async def test_memory_write_after_tool_execution(
        self,
        mock_db
    ):
        """Test that memory writes occur after tool execution."""
        # Create a single mock LLM
        mock_llm = MagicMock()
        mock_llm.llm_chat = MagicMock()
        
        call_count = [0]
        def llm_chat_side_effect(*args, **kwargs):
            count = call_count[0]
            call_count[0] += 1
            if count == 0:
                return {"intent": "summarization", "confidence": 0.95, "extracted_info": {}}
            elif count == 1:
                return {"steps": ["Summarize"]}
            elif count == 2:
                return {"summary": "Test summary", "decisions": []}
            elif count == 3:
                return "Summary response"
            else:
                return "Default response"
        
        mock_llm.llm_chat.side_effect = llm_chat_side_effect
        
        with patch('app.orchestrator.agent.GeminiClient', return_value=mock_llm), \
             patch('app.orchestrator.intent_recognition.GeminiClient', return_value=mock_llm), \
             patch('app.orchestrator.workflow_planning.GeminiClient', return_value=mock_llm), \
             patch('app.orchestrator.output_synthesis.GeminiClient', return_value=mock_llm), \
             patch('app.tools.summarization.GeminiClient', return_value=mock_llm), \
             patch('app.orchestrator.agent.MemoryRepository') as mock_memory_class, \
             patch('app.orchestrator.agent.IntegrationDataFetcher') as mock_fetcher_class:
            
            mock_memory = MagicMock()
            mock_memory_class.return_value = mock_memory
            mock_memory.get_relevant_memories.return_value = []
            mock_memory.get_client_context.return_value = {}
            mock_memory.get_meeting_by_id.return_value = None
            mock_memory.save_interaction_memory = MagicMock()
            
            mock_fetcher = MagicMock()
            mock_fetcher_class.return_value = mock_fetcher
            mock_fetcher.process_calendar_event_for_summarization = AsyncMock(return_value={
                "meeting_title": "Test Meeting",
                "meeting_date": "May 01, 2024",
                "transcript": "Test transcript",
                "has_transcript": True,
                "meeting_id": None
            })
            
            orchestrator = AgentOrchestrator(mock_db)
            await orchestrator.process_message(
                message="Summarize meeting",
                user_id=1
            )
            
            # Verify memory write was called
            mock_memory.save_interaction_memory.assert_called_once()

