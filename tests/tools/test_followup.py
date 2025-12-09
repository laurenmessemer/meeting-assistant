"""Tests for FollowUpTool."""

import pytest
from unittest.mock import MagicMock
from app.tools.followup import FollowUpTool
from app.llm.gemini_client import GeminiClient


class TestFollowUpTool:
    """Tests for FollowUpTool.generate_followup()."""
    
    @pytest.fixture
    def mock_llm_client(self):
        """Create a mock LLM client."""
        client = MagicMock(spec=GeminiClient)
        client.llm_chat = MagicMock()  # llm_chat is not async
        return client
    
    @pytest.fixture
    def followup_tool(self, mock_llm_client):
        """Create a FollowUpTool instance with mocked LLM."""
        return FollowUpTool(mock_llm_client)
    
    @pytest.mark.asyncio
    async def test_generate_followup_with_full_data(self, followup_tool, mock_llm_client):
        """Test follow-up generation with all fields provided."""
        # Mock LLM response
        mock_llm_client.llm_chat.return_value = {
            "subject": "Follow-up: Test Meeting",
            "body": "Thank you for the meeting. Here are the key points..."
        }
        
        result = await followup_tool.generate_followup(
            meeting_summary="Meeting summary text",
            transcript="Full transcript text",
            meeting_title="Test Meeting",
            meeting_date="November 21, 2024 at 10:00 AM",
            client_name="Test Client",
            client_email="client@example.com",
            attendees="John Doe, Jane Smith",
            action_items=["Action 1", "Action 2"],
            decisions=[{"description": "Decision 1", "context": "Context 1"}]
        )
        
        # Verify LLM was called
        assert mock_llm_client.llm_chat.called
        call_args = mock_llm_client.llm_chat.call_args
        assert call_args.kwargs["response_format"] == "JSON"
        assert call_args.kwargs["temperature"] == 0.7
        
        # Verify result structure
        assert result["subject"] == "Follow-up: Test Meeting"
        assert result["body"] == "Thank you for the meeting. Here are the key points..."
        assert result["client_name"] == "Test Client"
        assert result["client_email"] == "client@example.com"
    
    @pytest.mark.asyncio
    async def test_generate_followup_with_minimal_data(self, followup_tool, mock_llm_client):
        """Test follow-up generation with minimal required fields."""
        mock_llm_client.llm_chat.return_value = {
            "subject": "Follow-up: Meeting Summary",
            "body": "Thank you for the meeting."
        }
        
        result = await followup_tool.generate_followup(
            meeting_summary="Basic summary"
        )
        
        assert mock_llm_client.llm_chat.called
        assert result["subject"] == "Follow-up: Meeting Summary"
        assert result["body"] == "Thank you for the meeting."
    
    @pytest.mark.asyncio
    async def test_generate_followup_with_decisions_list(self, followup_tool, mock_llm_client):
        """Test follow-up generation with decisions as list of dicts."""
        mock_llm_client.llm_chat.return_value = {
            "subject": "Follow-up: Meeting",
            "body": "Email body"
        }
        
        decisions = [
            {"description": "Decision 1", "context": "Context 1"},
            {"description": "Decision 2", "context": None}
        ]
        
        result = await followup_tool.generate_followup(
            meeting_summary="Summary",
            decisions=decisions
        )
        
        # Verify prompt includes decisions
        call_args = mock_llm_client.llm_chat.call_args
        prompt = call_args.kwargs["prompt"]
        assert "Decision 1" in prompt
        assert "Context 1" in prompt
        assert "Decision 2" in prompt
        
        # Subject uses fallback format when meeting_title is None
        assert "Follow-up" in result["subject"]
    
    @pytest.mark.asyncio
    async def test_generate_followup_json_parsing_fallback(self, followup_tool, mock_llm_client):
        """Test fallback when JSON parsing fails."""
        # Mock LLM returning non-dict (shouldn't happen but test fallback)
        mock_llm_client.llm_chat.return_value = "Not a dict"
        
        result = await followup_tool.generate_followup(
            meeting_summary="Summary",
            meeting_title="Test Meeting"
        )
        
        # Should use fallback subject
        assert result["subject"] == "Follow-up: Test Meeting"
        assert result["body"] == "Not a dict"
    
    @pytest.mark.asyncio
    async def test_generate_followup_includes_meeting_date_and_attendees(self, followup_tool, mock_llm_client):
        """Test that meeting_date and attendees are included in prompt."""
        mock_llm_client.llm_chat.return_value = {
            "subject": "Follow-up",
            "body": "Body"
        }
        
        await followup_tool.generate_followup(
            meeting_summary="Summary",
            meeting_title="Meeting",
            meeting_date="November 21, 2024 at 10:00 AM",
            attendees="John Doe, Jane Smith"
        )
        
        # Verify prompt includes date and attendees
        call_args = mock_llm_client.llm_chat.call_args
        prompt = call_args.kwargs["prompt"]
        assert "November 21, 2024 at 10:00 AM" in prompt
        assert "John Doe, Jane Smith" in prompt
    
    @pytest.mark.asyncio
    async def test_generate_followup_handles_missing_transcript(self, followup_tool, mock_llm_client):
        """Test that missing transcript doesn't break generation."""
        mock_llm_client.llm_chat.return_value = {
            "subject": "Follow-up: Meeting Summary",
            "body": "Body"
        }
        
        result = await followup_tool.generate_followup(
            meeting_summary="Summary",
            transcript=None
        )
        
        assert result["subject"] == "Follow-up: Meeting Summary"
        # Verify transcript section not in prompt when None
        call_args = mock_llm_client.llm_chat.call_args
        prompt = call_args.kwargs["prompt"]
        # When transcript is None, it should not appear in the prompt
        assert "Full Transcript (for additional context):" not in prompt

