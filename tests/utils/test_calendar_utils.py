"""Tests for calendar utility functions."""

import pytest
from datetime import datetime, timezone
from app.utils.calendar_utils import (
    extract_attendees,
    sort_events_by_date
)


class TestExtractAttendees:
    """Tests for extract_attendees() function."""
    
    def test_handles_attendees_with_displayname(self):
        """Test extracting attendees with displayName."""
        event = {
            'attendees': [
                {'displayName': 'John Doe', 'email': 'john@example.com'},
                {'displayName': 'Jane Smith', 'email': 'jane@example.com'}
            ]
        }
        result = extract_attendees(event)
        assert result == "John Doe, Jane Smith"
    
    def test_falls_back_to_email(self):
        """Test that email is used when displayName is missing."""
        event = {
            'attendees': [
                {'email': 'john@example.com'},
                {'displayName': 'Jane Smith', 'email': 'jane@example.com'}
            ]
        }
        result = extract_attendees(event)
        assert 'john@example.com' in result
        assert 'Jane Smith' in result
    
    def test_returns_not_specified_when_empty(self):
        """Test that empty attendees list returns 'Not specified'."""
        event = {'attendees': []}
        result = extract_attendees(event)
        assert result == "Not specified"
    
    def test_returns_not_specified_when_no_attendees_field(self):
        """Test that missing attendees field returns 'Not specified'."""
        event = {}
        result = extract_attendees(event)
        assert result == "Not specified"
    
    def test_returns_not_specified_for_none_event(self):
        """Test that None event returns 'Not specified'."""
        result = extract_attendees(None)
        assert result == "Not specified"
    
    def test_handles_attendees_without_name_or_email(self):
        """Test that attendees without name or email are skipped."""
        event = {
            'attendees': [
                {'displayName': 'John Doe'},
                {},  # Empty attendee
                {'email': 'jane@example.com'}
            ]
        }
        result = extract_attendees(event)
        assert 'John Doe' in result
        assert 'jane@example.com' in result
        # Should not have empty strings
    
    def test_handles_mixed_attendees(self):
        """Test handling mix of displayName and email-only attendees."""
        event = {
            'attendees': [
                {'displayName': 'John Doe'},
                {'email': 'jane@example.com'},
                {'displayName': 'Bob Smith', 'email': 'bob@example.com'}
            ]
        }
        result = extract_attendees(event)
        assert 'John Doe' in result
        assert 'jane@example.com' in result
        assert 'Bob Smith' in result


class TestSortEventsByDate:
    """Tests for sort_events_by_date() function."""
    
    def test_correctly_sorts_events_newest_to_oldest(self):
        """Test that events are sorted newest first (reverse=True)."""
        events = [
            {'start': {'dateTime': '2024-01-01T10:00:00Z'}},
            {'start': {'dateTime': '2024-03-01T10:00:00Z'}},
            {'start': {'dateTime': '2024-02-01T10:00:00Z'}}
        ]
        result = sort_events_by_date(events, reverse=True)
        
        assert len(result) == 3
        assert result[0]['start']['dateTime'] == '2024-03-01T10:00:00Z'
        assert result[1]['start']['dateTime'] == '2024-02-01T10:00:00Z'
        assert result[2]['start']['dateTime'] == '2024-01-01T10:00:00Z'
    
    def test_sorts_oldest_to_newest_when_reverse_false(self):
        """Test that events are sorted oldest first when reverse=False."""
        events = [
            {'start': {'dateTime': '2024-03-01T10:00:00Z'}},
            {'start': {'dateTime': '2024-01-01T10:00:00Z'}},
            {'start': {'dateTime': '2024-02-01T10:00:00Z'}}
        ]
        result = sort_events_by_date(events, reverse=False)
        
        assert len(result) == 3
        assert result[0]['start']['dateTime'] == '2024-01-01T10:00:00Z'
        assert result[1]['start']['dateTime'] == '2024-02-01T10:00:00Z'
        assert result[2]['start']['dateTime'] == '2024-03-01T10:00:00Z'
    
    def test_handles_events_missing_dates(self):
        """Test that events without dates are placed at the end."""
        events = [
            {'start': {'dateTime': '2024-02-01T10:00:00Z'}},
            {'start': {}},  # Missing date
            {'start': {'dateTime': '2024-01-01T10:00:00Z'}},
            {}  # No start field
        ]
        result = sort_events_by_date(events, reverse=True)
        
        assert len(result) == 4
        # Events with dates should come first
        assert result[0]['start']['dateTime'] == '2024-02-01T10:00:00Z'
        assert result[1]['start']['dateTime'] == '2024-01-01T10:00:00Z'
        # Events without dates should be at the end
        assert 'dateTime' not in result[2].get('start', {})
        assert 'start' not in result[3] or 'dateTime' not in result[3].get('start', {})
    
    def test_ensures_stable_sorting_same_timestamps(self):
        """Test that events with same timestamps maintain stable order."""
        events = [
            {'id': '1', 'start': {'dateTime': '2024-01-01T10:00:00Z'}},
            {'id': '2', 'start': {'dateTime': '2024-01-01T10:00:00Z'}},
            {'id': '3', 'start': {'dateTime': '2024-01-01T10:00:00Z'}}
        ]
        result = sort_events_by_date(events, reverse=True)
        
        # All have same timestamp, so order should be preserved (stable sort)
        assert len(result) == 3
        # Python's sorted() is stable, so original order should be maintained
        # for items with equal keys
        ids = [event['id'] for event in result]
        assert ids == ['1', '2', '3']
    
    def test_handles_empty_list(self):
        """Test that empty list returns empty list."""
        result = sort_events_by_date([], reverse=True)
        assert result == []
    
    def test_handles_date_only_events(self):
        """Test sorting events with date-only (all-day events)."""
        events = [
            {'start': {'date': '2024-03-01'}},
            {'start': {'date': '2024-01-01'}},
            {'start': {'date': '2024-02-01'}}
        ]
        result = sort_events_by_date(events, reverse=True)
        
        assert len(result) == 3
        assert result[0]['start']['date'] == '2024-03-01'
        assert result[1]['start']['date'] == '2024-02-01'
        assert result[2]['start']['date'] == '2024-01-01'
    
    def test_handles_mixed_datetime_and_date(self):
        """Test sorting events with both dateTime and date fields."""
        events = [
            {'start': {'date': '2024-01-01'}},
            {'start': {'dateTime': '2024-02-01T10:00:00Z'}},
            {'start': {'date': '2024-03-01'}}
        ]
        result = sort_events_by_date(events, reverse=True)
        
        assert len(result) == 3
        # dateTime events should be sorted correctly
        assert result[0]['start']['date'] == '2024-03-01'
        assert result[1]['start']['dateTime'] == '2024-02-01T10:00:00Z'
        assert result[2]['start']['date'] == '2024-01-01'

