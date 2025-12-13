"""Unit tests for last meeting auto-resolution."""

import pytest
from unittest.mock import MagicMock, patch
from app.orchestrator.last_meeting_resolver import resolve_last_meeting


class TestLastMeetingResolver:
    """Tests for resolve_last_meeting function."""
    
    def test_auto_resolves_when_all_conditions_met(self):
        """Test that resolver auto-selects when all conditions are met."""
        message = "Summarize my last meeting with MTCA"
        intent = "summarization"
        target_date = None
        meeting_options = [
            MagicMock(calendar_event_id="event_1", title="Meeting 1"),
            MagicMock(calendar_event_id="event_2", title="Meeting 2"),
        ]
        
        mock_calendar_event = {"id": "event_1", "summary": "Meeting 1"}
        
        with patch('app.orchestrator.last_meeting_resolver.get_calendar_event_by_id') as mock_get:
            mock_get.return_value = mock_calendar_event
            
            result = resolve_last_meeting(message, intent, target_date, meeting_options)
            
            assert result == mock_calendar_event
            mock_get.assert_called_once_with("event_1")
    
    def test_does_not_resolve_when_intent_not_summarization(self):
        """Test that resolver does not resolve for non-summarization intents."""
        message = "Summarize my last meeting"
        intent = "meeting_brief"
        target_date = None
        meeting_options = [
            MagicMock(calendar_event_id="event_1"),
            MagicMock(calendar_event_id="event_2"),
        ]
        
        result = resolve_last_meeting(message, intent, target_date, meeting_options)
        
        assert result is None
    
    def test_does_not_resolve_when_target_date_provided(self):
        """Test that resolver does not resolve when target_date is provided."""
        from datetime import datetime
        message = "Summarize my last meeting"
        intent = "summarization"
        target_date = datetime(2024, 10, 29)
        meeting_options = [
            MagicMock(calendar_event_id="event_1"),
            MagicMock(calendar_event_id="event_2"),
        ]
        
        result = resolve_last_meeting(message, intent, target_date, meeting_options)
        
        assert result is None
    
    def test_does_not_resolve_when_single_option(self):
        """Test that resolver does not resolve when only one option exists."""
        message = "Summarize my last meeting"
        intent = "summarization"
        target_date = None
        meeting_options = [
            MagicMock(calendar_event_id="event_1"),
        ]
        
        result = resolve_last_meeting(message, intent, target_date, meeting_options)
        
        assert result is None
    
    def test_does_not_resolve_when_no_recency_language(self):
        """Test that resolver does not resolve without recency language."""
        message = "Summarize my meeting with MTCA"
        intent = "summarization"
        target_date = None
        meeting_options = [
            MagicMock(calendar_event_id="event_1"),
            MagicMock(calendar_event_id="event_2"),
        ]
        
        result = resolve_last_meeting(message, intent, target_date, meeting_options)
        
        assert result is None
    
    def test_resolves_with_different_recency_keywords(self):
        """Test that resolver works with different recency keywords."""
        test_cases = [
            ("Summarize my last meeting", "last"),
            ("Summarize my latest meeting", "latest"),
            ("Summarize my most recent meeting", "most recent"),
            ("Summarize my most-recent meeting", "most-recent"),
        ]
        
        for message, keyword in test_cases:
            intent = "summarization"
            target_date = None
            meeting_options = [
                MagicMock(calendar_event_id="event_1"),
                MagicMock(calendar_event_id="event_2"),
            ]
            
            mock_calendar_event = {"id": "event_1", "summary": "Meeting 1"}
            
            with patch('app.orchestrator.last_meeting_resolver.get_calendar_event_by_id') as mock_get:
                mock_get.return_value = mock_calendar_event
                
                result = resolve_last_meeting(message, intent, target_date, meeting_options)
                
                assert result == mock_calendar_event, f"Failed for keyword: {keyword}"
    
    def test_handles_dict_meeting_options(self):
        """Test that resolver handles MeetingOption as dict."""
        message = "Summarize my last meeting"
        intent = "summarization"
        target_date = None
        meeting_options = [
            {"calendar_event_id": "event_1", "title": "Meeting 1"},
            {"calendar_event_id": "event_2", "title": "Meeting 2"},
        ]
        
        mock_calendar_event = {"id": "event_1", "summary": "Meeting 1"}
        
        with patch('app.orchestrator.last_meeting_resolver.get_calendar_event_by_id') as mock_get:
            mock_get.return_value = mock_calendar_event
            
            result = resolve_last_meeting(message, intent, target_date, meeting_options)
            
            assert result == mock_calendar_event
            mock_get.assert_called_once_with("event_1")
    
    def test_returns_none_when_calendar_event_id_missing(self):
        """Test that resolver returns None when calendar_event_id is missing."""
        message = "Summarize my last meeting"
        intent = "summarization"
        target_date = None
        meeting_options = [
            MagicMock(calendar_event_id=None),  # Missing ID
            MagicMock(calendar_event_id="event_2"),
        ]
        
        result = resolve_last_meeting(message, intent, target_date, meeting_options)
        
        assert result is None
    
    def test_returns_none_when_fetch_fails(self):
        """Test that resolver returns None when calendar event fetch fails."""
        message = "Summarize my last meeting"
        intent = "summarization"
        target_date = None
        meeting_options = [
            MagicMock(calendar_event_id="event_1"),
            MagicMock(calendar_event_id="event_2"),
        ]
        
        with patch('app.orchestrator.last_meeting_resolver.get_calendar_event_by_id') as mock_get:
            mock_get.return_value = None  # Fetch fails
            
            result = resolve_last_meeting(message, intent, target_date, meeting_options)
            
            assert result is None
    
    def test_returns_none_when_fetch_raises_exception(self):
        """Test that resolver returns None when calendar event fetch raises exception."""
        message = "Summarize my last meeting"
        intent = "summarization"
        target_date = None
        meeting_options = [
            MagicMock(calendar_event_id="event_1"),
            MagicMock(calendar_event_id="event_2"),
        ]
        
        with patch('app.orchestrator.last_meeting_resolver.get_calendar_event_by_id') as mock_get:
            mock_get.side_effect = Exception("API error")
            
            result = resolve_last_meeting(message, intent, target_date, meeting_options)
            
            assert result is None
    
    def test_case_insensitive_recency_detection(self):
        """Test that recency language detection is case-insensitive."""
        message = "SUMMARIZE MY LAST MEETING"
        intent = "summarization"
        target_date = None
        meeting_options = [
            MagicMock(calendar_event_id="event_1"),
            MagicMock(calendar_event_id="event_2"),
        ]
        
        mock_calendar_event = {"id": "event_1", "summary": "Meeting 1"}
        
        with patch('app.orchestrator.last_meeting_resolver.get_calendar_event_by_id') as mock_get:
            mock_get.return_value = mock_calendar_event
            
            result = resolve_last_meeting(message, intent, target_date, meeting_options)
            
            assert result == mock_calendar_event

