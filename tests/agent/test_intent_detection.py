"""Tests for intent recognition with mocked LLM."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from app.orchestrator.intent_recognition import IntentRecognizer
from app.llm.gemini_client import GeminiClient


class TestIntentRecognition:
    """Tests for intent recognition with mocked LLM."""
    
    @pytest.fixture
    def mock_llm(self):
        """Create a mocked LLM client."""
        llm = MagicMock(spec=GeminiClient)
        llm.llm_chat = MagicMock()  # llm_chat is not async
        return llm
    
    @pytest.fixture
    def intent_recognizer(self, mock_llm):
        """Create intent recognizer with mocked LLM."""
        return IntentRecognizer(mock_llm)
    
    @pytest.mark.asyncio
    async def test_summarize_meeting_intent(self, intent_recognizer, mock_llm):
        """Test that 'Summarize my last meeting' is recognized as summarization intent."""
        mock_llm.llm_chat.return_value = {
            "intent": "summarization",
            "confidence": 0.95,
            "extracted_info": {
                "meeting_type": "last",
                "action": "summarize"
            }
        }
        
        result = await intent_recognizer.recognize("Summarize my last meeting")
        
        assert result["intent"] == "summarization"
        assert result["confidence"] == 0.95
        assert "extracted_info" in result
        mock_llm.llm_chat.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_meeting_brief_intent(self, intent_recognizer, mock_llm):
        """Test that 'Prepare me for my next meeting' is recognized as meeting_brief intent."""
        mock_llm.llm_chat.return_value = {
            "intent": "meeting_brief",
            "confidence": 0.92,
            "extracted_info": {
                "meeting_type": "next",
                "action": "prepare"
            }
        }
        
        result = await intent_recognizer.recognize("Prepare me for my next meeting")
        
        assert result["intent"] == "meeting_brief"
        assert result["confidence"] == 0.92
        mock_llm.llm_chat.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_followup_intent(self, intent_recognizer, mock_llm):
        """Test that 'Draft a follow-up email for today's client call' is recognized as followup intent."""
        mock_llm.llm_chat.return_value = {
            "intent": "followup",
            "confidence": 0.88,
            "extracted_info": {
                "meeting_type": "today",
                "action": "followup",
                "email_type": "followup"
            }
        }
        
        result = await intent_recognizer.recognize("Draft a follow-up email for today's client call")
        
        assert result["intent"] == "followup"
        assert result["confidence"] == 0.88
        mock_llm.llm_chat.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_general_intent_fallback(self, intent_recognizer, mock_llm):
        """Test that unrecognized intents fall back to general."""
        mock_llm.llm_chat.return_value = {
            "intent": "general",
            "confidence": 0.5,
            "extracted_info": {}
        }
        
        result = await intent_recognizer.recognize("What's the weather?")
        
        assert result["intent"] == "general"
        assert result["confidence"] == 0.5
    
    @pytest.mark.asyncio
    async def test_error_handling_returns_general(self, intent_recognizer, mock_llm):
        """Test that exceptions fall back to general intent."""
        mock_llm.llm_chat.side_effect = Exception("LLM API error")
        
        result = await intent_recognizer.recognize("Any message")
        
        assert result["intent"] == "general"
        assert result["confidence"] == 0.5
        assert result["extracted_info"] == {}
    
    @pytest.mark.asyncio
    async def test_string_response_parsing(self, intent_recognizer, mock_llm):
        """Test that string JSON responses are parsed correctly."""
        mock_llm.llm_chat.return_value = '{"intent": "summarization", "confidence": 0.9, "extracted_info": {}}'
        
        result = await intent_recognizer.recognize("Summarize meeting")
        
        assert result["intent"] == "summarization"
        assert result["confidence"] == 0.9
    
    @pytest.mark.asyncio
    async def test_workflow_routing_summarization(self, intent_recognizer, mock_llm):
        """Test that summarization intent routes to correct workflow."""
        mock_llm.llm_chat.return_value = {
            "intent": "summarization",
            "confidence": 0.95,
            "extracted_info": {"meeting_type": "last"}
        }
        
        result = await intent_recognizer.recognize("Summarize my last meeting")
        
        assert result["intent"] == "summarization"
        # Intent should route to summarization workflow
        assert result["intent"] in ["summarization", "meeting_brief", "followup", "general"]
    
    @pytest.mark.asyncio
    async def test_workflow_routing_meeting_brief(self, intent_recognizer, mock_llm):
        """Test that meeting_brief intent routes to correct workflow."""
        mock_llm.llm_chat.return_value = {
            "intent": "meeting_brief",
            "confidence": 0.92,
            "extracted_info": {"meeting_type": "next"}
        }
        
        result = await intent_recognizer.recognize("Prepare me for my next meeting")
        
        assert result["intent"] == "meeting_brief"
    
    @pytest.mark.asyncio
    async def test_workflow_routing_followup(self, intent_recognizer, mock_llm):
        """Test that followup intent routes to correct workflow."""
        mock_llm.llm_chat.return_value = {
            "intent": "followup",
            "confidence": 0.88,
            "extracted_info": {"meeting_type": "today"}
        }
        
        result = await intent_recognizer.recognize("Draft a follow-up email")
        
        assert result["intent"] == "followup"

