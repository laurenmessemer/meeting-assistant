# Duplication Analysis Report

This report identifies duplicated functions and logic patterns across the project and proposes safe deduplication steps.

## Summary

Found **5 major duplication patterns** across **6 files**:
1. Date/Time parsing from ISO format strings
2. Date formatting to display strings
3. Calendar event date extraction
4. Attendee extraction from calendar events
5. Event sorting by date

---

## 1. Date/Time Parsing from ISO Format Strings

### Duplication Locations

**Pattern**: Parsing ISO format date strings with timezone handling
```python
if 'T' in date_str:
    dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
else:
    dt = datetime.fromisoformat(date_str)
if dt.tzinfo is None:
    dt = dt.replace(tzinfo=timezone.utc)
else:
    dt = dt.astimezone(timezone.utc)
```

**Found in:**
- `app/orchestrator/integration_data_fetching.py` (lines 81-87, 131-133, 188-190)
- `app/integrations/google_calendar_client.py` (lines 24, 27, 39, 299, 314, 326, 330, 339, 346, 459, 463, 466, 475)
- `app/integrations/zoom_client.py` (lines 130, 132, 220, 222, 575, 577)
- `app/orchestrator/meeting_finder.py` (lines 384-395)

**Impact**: High - This pattern appears **20+ times** across the codebase

### Proposed Solution

**Create**: `app/utils/date_utils.py`
```python
def parse_iso_datetime(date_str: str, default_tz: timezone = timezone.utc) -> Optional[datetime]:
    """Parse ISO format datetime string with timezone handling."""
    if not date_str:
        return None
    try:
        if 'T' in date_str:
            dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        else:
            dt = datetime.fromisoformat(date_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=default_tz)
        else:
            dt = dt.astimezone(default_tz)
        return dt
    except (ValueError, AttributeError):
        return None
```

**Refactoring Steps:**
1. Create `app/utils/date_utils.py` with `parse_iso_datetime()` function
2. Replace all occurrences in `integration_data_fetching.py` (3 locations)
3. Replace all occurrences in `google_calendar_client.py` (13 locations)
4. Replace all occurrences in `zoom_client.py` (6 locations)
5. Replace occurrence in `meeting_finder.py` (1 location)
6. Test each file after replacement

**Risk**: Low - Pure function, no side effects

---

## 2. Date Formatting to Display Strings

### Duplication Locations

**Pattern**: Formatting datetime to human-readable string
```python
dt.strftime("%B %d, %Y at %I:%M %p")
```

**Found in:**
- `app/orchestrator/integration_data_fetching.py` (lines 109, 191)
- `app/orchestrator/tool_execution.py` (lines 100-101)

**Impact**: Medium - Appears **3 times**

### Proposed Solution

**Add to**: `app/utils/date_utils.py`
```python
def format_datetime_display(dt: Optional[datetime], default: str = "Unknown date") -> str:
    """Format datetime to human-readable display string."""
    if not dt:
        return default
    try:
        return dt.strftime("%B %d, %Y at %I:%M %p")
    except (AttributeError, ValueError):
        return default
```

**Refactoring Steps:**
1. Add `format_datetime_display()` to `date_utils.py`
2. Replace in `integration_data_fetching.py` (2 locations)
3. Replace in `tool_execution.py` (2 locations)
4. Test date formatting in UI

**Risk**: Low - Simple formatting function

---

## 3. Calendar Event Date Extraction

### Duplication Locations

**Pattern**: Extracting and parsing date from calendar event start time
```python
event_start = event.get('start', {})
start_time_str = event_start.get('dateTime') or event_start.get('date')
# Then parse with ISO format logic
```

**Found in:**
- `app/orchestrator/integration_data_fetching.py` (lines 74-89, 182-193)
- `app/integrations/google_calendar_client.py` (in `_is_event_in_past()` function, lines 11-12)

**Impact**: Medium - Appears **3 times**

### Proposed Solution

**Add to**: `app/utils/date_utils.py`
```python
def extract_event_datetime(event: Dict[str, Any]) -> Optional[datetime]:
    """Extract datetime from Google Calendar event."""
    event_start = event.get('start', {})
    start_time_str = event_start.get('dateTime') or event_start.get('date')
    if not start_time_str:
        return None
    return parse_iso_datetime(start_time_str)
```

**Refactoring Steps:**
1. Add `extract_event_datetime()` to `date_utils.py`
2. Replace in `integration_data_fetching.py` (2 locations)
3. Update `google_calendar_client.py` `_is_event_in_past()` to use it
4. Test calendar event processing

**Risk**: Low - Extracts common pattern

---

## 4. Attendee Extraction from Calendar Events

### Duplication Locations

**Pattern**: Extracting attendee names from calendar event
```python
event_attendees = event.get('attendees', [])
attendee_names = [att.get('displayName') or att.get('email', '') for att in event_attendees]
attendees = ", ".join([a for a in attendee_names if a])
```

**Found in:**
- `app/orchestrator/integration_data_fetching.py` (lines 102-107, 196-198)

**Impact**: Low - Appears **2 times** in same file

### Proposed Solution

**Add to**: `app/utils/calendar_utils.py` (new file)
```python
def extract_attendees(event: Dict[str, Any]) -> str:
    """Extract attendee names from calendar event."""
    event_attendees = event.get('attendees', [])
    attendee_names = [att.get('displayName') or att.get('email', '') for att in event_attendees]
    attendees = ", ".join([a for a in attendee_names if a])
    return attendees if attendees else "Not specified"
```

**Refactoring Steps:**
1. Create `app/utils/calendar_utils.py`
2. Add `extract_attendees()` function
3. Replace both occurrences in `integration_data_fetching.py`
4. Test attendee display in UI

**Risk**: Low - Simple extraction function

---

## 5. Event Sorting by Date

### Duplication Locations

**Pattern**: Sorting calendar events by date (most recent first)
```python
def get_event_date(event):
    start = event.get('start', {})
    date_time = start.get('dateTime') or start.get('date', '')
    # Complex parsing logic...
    return dt

sorted_events = sorted(events, key=get_event_date, reverse=True)
```

**Found in:**
- `app/orchestrator/meeting_finder.py` (lines 372-400)

**Impact**: Low - Appears **1 time** but uses duplicated date parsing logic

### Proposed Solution

**Add to**: `app/utils/calendar_utils.py`
```python
def sort_events_by_date(events: List[Dict[str, Any]], reverse: bool = True) -> List[Dict[str, Any]]:
    """Sort calendar events by date."""
    from app.utils.date_utils import extract_event_datetime
    
    def get_event_date(event):
        dt = extract_event_datetime(event)
        if not dt:
            return datetime.min.replace(tzinfo=timezone.utc)
        return dt
    
    return sorted(events, key=get_event_date, reverse=reverse)
```

**Refactoring Steps:**
1. Add `sort_events_by_date()` to `calendar_utils.py`
2. Replace `_sort_events_by_date()` in `meeting_finder.py`
3. Test meeting finder functionality

**Risk**: Low - Uses existing date extraction utility

---

## Implementation Plan

### Phase 1: Create Utility Modules (Low Risk)
1. ✅ Create `app/utils/__init__.py`
2. ✅ Create `app/utils/date_utils.py` with:
   - `parse_iso_datetime()`
   - `format_datetime_display()`
   - `extract_event_datetime()`
3. ✅ Create `app/utils/calendar_utils.py` with:
   - `extract_attendees()`
   - `sort_events_by_date()`

### Phase 2: Refactor Date Parsing (Medium Risk)
1. Replace date parsing in `integration_data_fetching.py`
2. Replace date parsing in `google_calendar_client.py`
3. Replace date parsing in `zoom_client.py`
4. Replace date parsing in `meeting_finder.py`
5. Test each file after changes

### Phase 3: Refactor Date Formatting (Low Risk)
1. Replace date formatting in `integration_data_fetching.py`
2. Replace date formatting in `tool_execution.py`
3. Test UI date display

### Phase 4: Refactor Calendar Utilities (Low Risk)
1. Replace attendee extraction in `integration_data_fetching.py`
2. Replace event sorting in `meeting_finder.py`
3. Test calendar event processing

### Phase 5: Cleanup
1. Remove unused imports
2. Run linter
3. Run full test suite
4. Update documentation

---

## Testing Strategy

For each refactoring step:
1. **Unit Tests**: Test utility functions in isolation
2. **Integration Tests**: Test affected modules with real data
3. **Regression Tests**: Verify existing functionality still works
4. **Edge Cases**: Test with None values, invalid dates, missing fields

---

## Estimated Impact

- **Lines of Code Reduced**: ~150-200 lines
- **Maintainability**: Significantly improved (single source of truth)
- **Bug Risk**: Reduced (fixes applied once affect all usages)
- **Test Coverage**: Easier to test utility functions

---

## Risk Assessment

| Refactoring | Risk Level | Reason |
|------------|-----------|--------|
| Date parsing utilities | Low | Pure functions, no side effects |
| Date formatting | Low | Simple formatting, easy to test |
| Calendar utilities | Low | Simple extraction/sorting logic |
| Overall | Low-Medium | Multiple files affected, but changes are isolated |

---

## Notes

- All utility functions should be pure (no side effects)
- All utility functions should handle None/empty values gracefully
- Consider adding type hints for better IDE support
- Add docstrings explaining expected input formats
- Consider adding unit tests for each utility function

