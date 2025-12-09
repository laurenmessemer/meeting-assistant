"""
Test event sorting for single-day calendar queries.

This test verifies that get_events_on_date():
1. Only queries the exact date range (2025-10-29)
2. Uses maxResults=50
3. Returns events sorted newest→oldest
4. Never returns events from wrong year (2024) when querying 2025
"""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime, date, timezone
from app.integrations.google_calendar_client import GoogleCalendarClient
from app.utils.date_utils import extract_event_datetime


class TestEventSortingForSingleDay:
    """Test event sorting and filtering for single-day queries."""
    
    def create_mock_event(self, event_id: str, summary: str, start_time: datetime) -> dict:
        """Create a mock Google Calendar event."""
        return {
            'id': event_id,
            'summary': summary,
            'start': {
                'dateTime': start_time.isoformat()
            },
            'end': {
                'dateTime': (start_time.replace(hour=start_time.hour + 1)).isoformat()
            }
        }
    
    def test_get_events_on_date_queries_exact_date_range(self):
        """
        Test that get_events_on_date() queries the exact 24-hour window.
        
        Verifies:
        - timeMin = YYYY-MM-DDT00:00:00Z
        - timeMax = YYYY-MM-DDT23:59:59Z
        - maxResults = 50
        """
        print("\n" + "="*80)
        print("TEST: get_events_on_date queries exact date range")
        print("="*80)
        
        target_date = date(2025, 10, 29)
        
        # Mock the Google Calendar API service
        mock_service = Mock()
        captured_params = []
        
        def mock_execute():
            result = Mock()
            result.get = lambda key, default=None: {
                'items': [],
                'nextPageToken': None
            }.get(key, default)
            return result
        
        mock_list = Mock()
        mock_list.execute = mock_execute
        
        def mock_list_call(**kwargs):
            captured_params.append(kwargs.copy())
            return mock_list
        
        mock_service.events.return_value.list = mock_list_call
        
        client = GoogleCalendarClient()
        client.service = mock_service
        
        events = client.get_events_on_date(target_date)
        
        print(f"\n[TEST RESULTS]")
        if captured_params:
            params = captured_params[0]
            time_min = params.get('timeMin', '')
            time_max = params.get('timeMax', '')
            max_results = params.get('maxResults')
            
            print(f"  timeMin: {time_min}")
            print(f"  timeMax: {time_max}")
            print(f"  maxResults: {max_results}")
            
            # Verify timeMin format
            assert time_min.startswith('2025-10-29T00:00:00'), \
                f"timeMin should start with '2025-10-29T00:00:00', got '{time_min}'"
            assert time_min.endswith('Z'), \
                f"timeMin should end with 'Z', got '{time_min}'"
            
            # Verify timeMax format
            assert '2025-10-29T23:59:59' in time_max or '2025-10-29T23:59:59' in time_max, \
                f"timeMax should contain '2025-10-29T23:59:59', got '{time_max}'"
            
            # Verify maxResults
            assert max_results == 50, \
                f"maxResults should be 50, got {max_results}"
            
            print(f"  ✓ timeMin format correct")
            print(f"  ✓ timeMax format correct")
            print(f"  ✓ maxResults = 50")
        else:
            pytest.fail("Could not capture request parameters")
        
        print("\n✓ TEST PASSED: Exact date range queried correctly")
    
    def test_get_events_on_date_only_returns_target_year_events(self):
        """
        Test that get_events_on_date() only returns events from the target year.
        
        Scenario:
        - Query for 2025-10-29
        - Mock returns events from both 2024-10-29 and 2025-10-29
        - Should only return 2025 events
        """
        print("\n" + "="*80)
        print("TEST: get_events_on_date only returns target year events")
        print("="*80)
        
        target_date = date(2025, 10, 29)
        
        # Create mock events: one from 2024, one from 2025
        event_2024 = self.create_mock_event(
            'event_2024',
            '2024 Meeting',
            datetime(2024, 10, 29, 10, 0, 0, tzinfo=timezone.utc)
        )
        
        event_2025 = self.create_mock_event(
            'event_2025',
            '2025 Meeting',
            datetime(2025, 10, 29, 10, 0, 0, tzinfo=timezone.utc)
        )
        
        # Mock service to return both events
        mock_service = Mock()
        
        def mock_execute():
            result = {
                'items': [event_2024, event_2025],
                'nextPageToken': None
            }
            # Create a mock that behaves like a dict
            mock_result = Mock()
            mock_result.get = lambda key, default=None: result.get(key, default)
            return mock_result
        
        mock_list = Mock()
        mock_list.execute = mock_execute
        mock_service.events.return_value.list.return_value = mock_list
        
        client = GoogleCalendarClient()
        client.service = mock_service
        
        events = client.get_events_on_date(target_date)
        
        print(f"\n[TEST RESULTS]")
        print(f"  Target date: {target_date} (year={target_date.year})")
        print(f"  Events returned: {len(events)}")
        
        # Extract years from returned events
        years = []
        for event in events:
            evt_dt = extract_event_datetime(event)
            if evt_dt:
                years.append(evt_dt.year)
                print(f"  Event: {event.get('summary')} - {evt_dt.date()} (year={evt_dt.year})")
        
        # Verify all events are from 2025
        assert all(year == 2025 for year in years), \
            f"All events should be from 2025, got years: {years}"
        
        # Verify 2024 event was filtered out
        assert len(events) == 1, \
            f"Should return 1 event (2025), got {len(events)}"
        assert events[0].get('summary') == '2025 Meeting', \
            f"Should return 2025 event, got {events[0].get('summary')}"
        
        print(f"  ✓ Only 2025 events returned")
        print(f"  ✓ 2024 event correctly filtered out")
        
        print("\n✓ TEST PASSED: Only target year events returned")
    
    def test_get_events_on_date_sorts_newest_to_oldest(self):
        """
        Test that get_events_on_date() sorts events newest→oldest.
        
        Scenario:
        - Query for 2025-10-29
        - Mock returns multiple events from same day
        - Should be sorted with newest (latest time) first
        """
        print("\n" + "="*80)
        print("TEST: get_events_on_date sorts newest→oldest")
        print("="*80)
        
        target_date = date(2025, 10, 29)
        
        # Create mock events at different times on the same day
        event_morning = self.create_mock_event(
            'event_morning',
            'Morning Meeting',
            datetime(2025, 10, 29, 9, 0, 0, tzinfo=timezone.utc)
        )
        
        event_afternoon = self.create_mock_event(
            'event_afternoon',
            'Afternoon Meeting',
            datetime(2025, 10, 29, 14, 0, 0, tzinfo=timezone.utc)
        )
        
        event_evening = self.create_mock_event(
            'event_evening',
            'Evening Meeting',
            datetime(2025, 10, 29, 18, 0, 0, tzinfo=timezone.utc)
        )
        
        # Mock service to return events (API returns in ascending order)
        mock_service = Mock()
        
        def mock_execute():
            result = {
                'items': [event_morning, event_afternoon, event_evening],
                'nextPageToken': None
            }
            # Create a mock that behaves like a dict
            mock_result = Mock()
            mock_result.get = lambda key, default=None: result.get(key, default)
            return mock_result
        
        mock_list = Mock()
        mock_list.execute = mock_execute
        mock_service.events.return_value.list.return_value = mock_list
        
        client = GoogleCalendarClient()
        client.service = mock_service
        
        events = client.get_events_on_date(target_date)
        
        print(f"\n[TEST RESULTS]")
        print(f"  Events returned: {len(events)}")
        
        # Extract timestamps
        timestamps = []
        for i, event in enumerate(events):
            evt_dt = extract_event_datetime(event)
            if evt_dt:
                timestamps.append(evt_dt)
                print(f"  Event[{i}]: {event.get('summary')} - {evt_dt}")
        
        # Verify sorting: should be newest→oldest (descending)
        assert len(timestamps) == 3, "Should have 3 events"
        
        # Check order: newest (evening) → oldest (morning)
        assert timestamps[0].hour == 18, \
            f"First event should be newest (evening, 18:00), got {timestamps[0].hour}:00"
        assert timestamps[1].hour == 14, \
            f"Second event should be afternoon (14:00), got {timestamps[1].hour}:00"
        assert timestamps[2].hour == 9, \
            f"Third event should be oldest (morning, 9:00), got {timestamps[2].hour}:00"
        
        # Verify descending order
        assert timestamps == sorted(timestamps, reverse=True), \
            "Events should be sorted newest→oldest (descending)"
        
        print(f"  ✓ Events sorted newest→oldest")
        print(f"  ✓ First event: {events[0].get('summary')} (newest)")
        print(f"  ✓ Last event: {events[-1].get('summary')} (oldest)")
        
        print("\n✓ TEST PASSED: Events sorted newest→oldest")
    
    def test_get_events_on_date_with_mixed_years_filters_correctly(self):
        """
        Test that get_events_on_date() correctly filters when API returns mixed years.
        
        Scenario:
        - Query for 2025-10-29
        - Mock API returns events from 2024-10-29 and 2025-10-29
        - Should filter to only 2025-10-29 events
        - Should sort 2025 events newest→oldest
        """
        print("\n" + "="*80)
        print("TEST: get_events_on_date filters mixed years correctly")
        print("="*80)
        
        target_date = date(2025, 10, 29)
        
        # Create mock events from both years
        event_2024_early = self.create_mock_event(
            'event_2024_early',
            '2024 Early Meeting',
            datetime(2024, 10, 29, 9, 0, 0, tzinfo=timezone.utc)
        )
        
        event_2024_late = self.create_mock_event(
            'event_2024_late',
            '2024 Late Meeting',
            datetime(2024, 10, 29, 15, 0, 0, tzinfo=timezone.utc)
        )
        
        event_2025_early = self.create_mock_event(
            'event_2025_early',
            '2025 Early Meeting',
            datetime(2025, 10, 29, 10, 0, 0, tzinfo=timezone.utc)
        )
        
        event_2025_late = self.create_mock_event(
            'event_2025_late',
            '2025 Late Meeting',
            datetime(2025, 10, 29, 16, 0, 0, tzinfo=timezone.utc)
        )
        
        # Mock service - API returns in ascending order (2024 first, then 2025)
        mock_service = Mock()
        
        def mock_execute():
            result = {
                'items': [event_2024_early, event_2024_late, event_2025_early, event_2025_late],
                'nextPageToken': None
            }
            # Create a mock that behaves like a dict
            mock_result = Mock()
            mock_result.get = lambda key, default=None: result.get(key, default)
            return mock_result
        
        mock_list = Mock()
        mock_list.execute = mock_execute
        mock_service.events.return_value.list.return_value = mock_list
        
        client = GoogleCalendarClient()
        client.service = mock_service
        
        events = client.get_events_on_date(target_date)
        
        print(f"\n[TEST RESULTS]")
        print(f"  Target date: {target_date} (year={target_date.year})")
        print(f"  Events returned: {len(events)}")
        
        # Extract years and timestamps
        years = []
        timestamps = []
        for event in events:
            evt_dt = extract_event_datetime(event)
            if evt_dt:
                years.append(evt_dt.year)
                timestamps.append(evt_dt)
                print(f"  Event: {event.get('summary')} - {evt_dt} (year={evt_dt.year})")
        
        # Verify only 2025 events returned
        assert all(year == 2025 for year in years), \
            f"All events should be from 2025, got years: {years}"
        
        assert len(events) == 2, \
            f"Should return 2 events (both 2025), got {len(events)}"
        
        # Verify sorting: newest→oldest
        assert timestamps == sorted(timestamps, reverse=True), \
            "Events should be sorted newest→oldest"
        
        # Verify newest event is first
        assert events[0].get('summary') == '2025 Late Meeting', \
            f"First event should be newest (Late Meeting), got {events[0].get('summary')}"
        
        print(f"  ✓ Only 2025 events returned")
        print(f"  ✓ Events sorted newest→oldest")
        print(f"  ✓ First event is newest (2025 Late Meeting)")
        
        print("\n✓ TEST PASSED: Mixed years filtered and sorted correctly")


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])

