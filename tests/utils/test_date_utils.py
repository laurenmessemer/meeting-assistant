"""Tests for date utility functions."""

import pytest
from datetime import datetime, timezone
from app.utils.date_utils import (
    parse_iso_datetime,
    format_datetime_display,
    extract_event_datetime
)


class TestParseIsoDatetime:
    """Tests for parse_iso_datetime() function."""
    
    def test_handles_normal_iso_string_with_z(self):
        """Test parsing ISO string with Z timezone."""
        result = parse_iso_datetime("2024-05-01T10:00:00Z")
        assert result is not None
        assert result.year == 2024
        assert result.month == 5
        assert result.day == 1
        assert result.hour == 10
        assert result.minute == 0
        assert result.second == 0
        assert result.tzinfo == timezone.utc
    
    def test_handles_naive_datetime(self):
        """Test parsing ISO string without timezone."""
        result = parse_iso_datetime("2024-05-01T10:00:00")
        assert result is not None
        assert result.year == 2024
        assert result.month == 5
        assert result.day == 1
        assert result.hour == 10
        assert result.tzinfo == timezone.utc  # Should default to UTC
    
    def test_handles_date_only(self):
        """Test parsing date-only string."""
        result = parse_iso_datetime("2024-05-01")
        assert result is not None
        assert result.year == 2024
        assert result.month == 5
        assert result.day == 1
        assert result.hour == 0
        assert result.minute == 0
        assert result.second == 0
        assert result.tzinfo == timezone.utc
    
    def test_handles_invalid_strings(self):
        """Test that invalid strings return None."""
        assert parse_iso_datetime("invalid") is None
        assert parse_iso_datetime("not-a-date") is None
        assert parse_iso_datetime("2024-13-45") is None  # Invalid date
        assert parse_iso_datetime("") is None
        assert parse_iso_datetime(None) is None
    
    def test_handles_timezone_offsets(self):
        """Test parsing with timezone offsets."""
        # Positive offset
        result = parse_iso_datetime("2024-05-01T10:00:00+05:00")
        assert result is not None
        assert result.tzinfo is not None
        
        # Negative offset
        result = parse_iso_datetime("2024-05-01T10:00:00-05:00")
        assert result is not None
        assert result.tzinfo is not None
        
        # Should convert to UTC
        result_utc = result.astimezone(timezone.utc)
        assert result_utc.tzinfo == timezone.utc
    
    def test_handles_plus_00_00_timezone(self):
        """Test parsing with +00:00 timezone."""
        result = parse_iso_datetime("2024-05-01T10:00:00+00:00")
        assert result is not None
        assert result.tzinfo == timezone.utc
    
    def test_custom_default_timezone(self):
        """Test with custom default timezone."""
        custom_tz = timezone.utc
        result = parse_iso_datetime("2024-05-01T10:00:00", default_tz=custom_tz)
        assert result is not None
        assert result.tzinfo == custom_tz


class TestFormatDatetimeDisplay:
    """Tests for format_datetime_display() function."""
    
    def test_formats_valid_datetimes_correctly(self):
        """Test formatting valid datetime objects."""
        dt = datetime(2024, 5, 1, 10, 30, 0, tzinfo=timezone.utc)
        result = format_datetime_display(dt)
        assert result == "May 01, 2024 at 10:30 AM"
        
        dt2 = datetime(2024, 11, 21, 14, 45, 0, tzinfo=timezone.utc)
        result2 = format_datetime_display(dt2)
        assert result2 == "November 21, 2024 at 02:45 PM"
    
    def test_returns_unknown_date_for_none(self):
        """Test that None returns default string."""
        result = format_datetime_display(None)
        assert result == "Unknown date"
    
    def test_returns_custom_default(self):
        """Test with custom default string."""
        result = format_datetime_display(None, default="No date available")
        assert result == "No date available"
    
    def test_handles_naive_datetime(self):
        """Test formatting naive datetime (no timezone)."""
        dt = datetime(2024, 5, 1, 10, 30, 0)
        result = format_datetime_display(dt)
        assert "May 01, 2024" in result
        assert "10:30 AM" in result
    
    def test_handles_invalid_datetime_gracefully(self):
        """Test that invalid datetime objects return default."""
        # This should not happen in practice, but test edge case
        class InvalidDatetime:
            pass
        
        invalid = InvalidDatetime()
        result = format_datetime_display(invalid)
        assert result == "Unknown date"


class TestExtractEventDatetime:
    """Tests for extract_event_datetime() function."""
    
    def test_extracts_from_event_with_datetime(self):
        """Test extracting datetime from event with dateTime field."""
        event = {
            'start': {
                'dateTime': '2024-05-01T10:00:00Z'
            }
        }
        result = extract_event_datetime(event)
        assert result is not None
        assert result.year == 2024
        assert result.month == 5
        assert result.day == 1
        assert result.tzinfo == timezone.utc
    
    def test_extracts_from_event_with_date(self):
        """Test extracting datetime from event with date field (all-day)."""
        event = {
            'start': {
                'date': '2024-05-01'
            }
        }
        result = extract_event_datetime(event)
        assert result is not None
        assert result.year == 2024
        assert result.month == 5
        assert result.day == 1
    
    def test_returns_none_for_missing_values(self):
        """Test that missing values return None."""
        # No start field
        assert extract_event_datetime({}) is None
        
        # Empty start field
        assert extract_event_datetime({'start': {}}) is None
        
        # No dateTime or date
        assert extract_event_datetime({'start': {'other': 'value'}}) is None
        
        # None event
        assert extract_event_datetime(None) is None
    
    def test_handles_invalid_date_strings(self):
        """Test that invalid date strings in event return None."""
        event = {
            'start': {
                'dateTime': 'invalid-date-string'
            }
        }
        result = extract_event_datetime(event)
        assert result is None
    
    def test_prefers_datetime_over_date(self):
        """Test that dateTime is preferred over date when both exist."""
        event = {
            'start': {
                'dateTime': '2024-05-01T10:00:00Z',
                'date': '2024-05-02'
            }
        }
        result = extract_event_datetime(event)
        assert result is not None
        assert result.day == 1  # Should use dateTime, not date
        assert result.hour == 10  # Should have time component

