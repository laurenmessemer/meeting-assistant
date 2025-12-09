# Architecture Violations Report

This report identifies violations of architectural boundaries in the meeting-assistant project.

## Summary

- **LLM calls outside llm/**: ✅ No violations found (tools and orchestrator components correctly use LLM client)
- **HubSpot/Google/Zoom logic outside integrations/**: ⚠️ 4 violations found
- **Business logic outside orchestrator/agent.py**: ⚠️ 2 violations found
- **Tools containing integration logic**: ⚠️ 3 violations found

---

## 1. LLM Calls Outside llm/

**Status**: ✅ **No violations found**

All LLM calls are properly contained:
- Tools receive `GeminiClient` as dependency injection
- Orchestrator components (intent_recognition, workflow_planning, memory_writing, output_synthesis) use LLM client correctly
- No direct LLM calls in API routes or other inappropriate locations

---

## 2. HubSpot/Google/Zoom Logic Outside integrations/

### Violation 1: `app/tools/summarization.py`
**Location**: Lines 359-482  
**Issue**: Direct instantiation and usage of `ZoomClient()`  
**Problematic Code Block**:
```python
# Line 361
zoom_client = ZoomClient()
print(f"   ✅ ZoomClient initialized successfully")

# Lines 376-482: Multiple Zoom API calls
uuid_result = await zoom_client.get_meeting_uuid_from_id(...)
transcript = await zoom_client.get_transcript_by_uuid(meeting_uuid)
transcript = await zoom_client.get_meeting_transcript_direct(zoom_meeting_id)
transcript = await zoom_client.get_meeting_transcript_from_recordings(...)
```

**Recommendation**: Inject `ZoomClient` as a dependency instead of creating it directly.

---

### Violation 2: `app/tools/meeting_brief.py`
**Location**: Lines 32-63  
**Issue**: Direct instantiation and usage of `ZoomClient()`  
**Problematic Code Block**:
```python
# Line 34
zoom_client = ZoomClient()

# Lines 38-61: Multiple Zoom API calls
previous_transcript = await zoom_client.get_meeting_transcript_direct(zoom_meeting_id)
meeting_uuid = await zoom_client.get_meeting_uuid_from_id(...)
previous_transcript = await zoom_client.get_transcript_by_uuid(meeting_uuid)
previous_transcript = await zoom_client.get_meeting_transcript_from_recordings(...)
```

**Recommendation**: Inject `ZoomClient` as a dependency instead of creating it directly.

---

### Violation 3: `app/tools/followup.py`
**Location**: Lines 40-71  
**Issue**: Direct instantiation and usage of `ZoomClient()`  
**Problematic Code Block**:
```python
# Line 42
zoom_client = ZoomClient()

# Lines 46-69: Multiple Zoom API calls
transcript = await zoom_client.get_meeting_transcript_direct(zoom_meeting_id)
meeting_uuid = await zoom_client.get_meeting_uuid_from_id(...)
transcript = await zoom_client.get_transcript_by_uuid(meeting_uuid)
transcript = await zoom_client.get_meeting_transcript_from_recordings(...)
```

**Recommendation**: Inject `ZoomClient` as a dependency instead of creating it directly.

---

### Violation 4: `app/orchestrator/agent.py`
**Location**: Lines 52-60  
**Issue**: Direct instantiation of `GoogleCalendarClient()`  
**Problematic Code Block**:
```python
def _get_calendar(self):
    """Get calendar client, initializing it if needed."""
    if self._calendar is None and self._calendar_error is None:
        try:
            self._calendar = GoogleCalendarClient()  # Line 56
        except Exception as e:
            self._calendar_error = str(e)
            self._calendar = None
    return self._calendar
```

**Note**: This is borderline acceptable since it's in the orchestrator, but it still violates the principle of keeping integration logic in `integrations/`. The calendar client is passed to tools, which is good, but the instantiation could be moved to a factory or dependency injection pattern.

**Recommendation**: Consider using a factory pattern or dependency injection for creating integration clients.

---

## 3. Business Logic Outside orchestrator/agent.py

### Violation 1: `app/orchestrator/tool_execution.py`
**Location**: Lines 125-745  
**Issue**: Extensive business logic for message parsing, date extraction, client name extraction, meeting finding, and workflow orchestration  
**Problematic Code Blocks**:

1. **Date Parsing Logic** (Lines 562-720):
   - Complex date parsing with multiple format support
   - Relative date handling (yesterday, today, tomorrow)
   - Written number conversion (twenty-first, etc.)

2. **Client Name Extraction** (Lines 315-375):
   - Multiple regex patterns for extracting client names
   - Normalization logic (uppercase acronyms, capitalization)
   - Common word filtering

3. **Meeting Selection Logic** (Lines 148-432):
   - Complex parsing of meeting identifiers from messages
   - Database and calendar search coordination
   - Meeting option creation and selection handling

4. **Message Parsing** (Lines 178-262):
   - Pattern matching for meeting numbers
   - Date detection to avoid false positives
   - Calendar event ID extraction

**Recommendation**: Move business logic to `orchestrator/agent.py` or create dedicated orchestrator modules (e.g., `orchestrator/message_parser.py`, `orchestrator/date_parser.py`).

---

### Violation 2: `app/tools/summarization.py`
**Location**: Lines 281-596  
**Issue**: Business logic for processing calendar events, coordinating Zoom transcript fetching, and meeting creation  
**Problematic Code Block**:
```python
async def _process_calendar_event(
    self,
    calendar_event: Dict[str, Any],
    client_name: Optional[str],
    user_id: Optional[int],
    client_id: Optional[int]
) -> Dict[str, Any]:
    """Process a calendar event: extract Zoom ID, fetch transcript, create meeting."""
    # Lines 281-596: Complex business logic including:
    # - Calendar event date parsing
    # - Zoom meeting ID extraction
    # - Multiple Zoom API call strategies (UUID-based, direct, recordings-based)
    # - Meeting database record creation
    # - Error handling and fallback logic
```

**Recommendation**: Move calendar event processing logic to `orchestrator/agent.py` or a dedicated orchestrator module. Tools should focus on their core functionality (summarization), not orchestration.

---

## 4. Tools Containing Integration Logic

### Violation 1: `app/tools/summarization.py`
**Location**: Lines 9, 359-482, 598-650  
**Issue**: Direct integration with Zoom API  
**Problematic Code Blocks**:

1. **Import** (Line 9):
   ```python
   from app.integrations.zoom_client import ZoomClient
   ```

2. **Direct ZoomClient instantiation** (Lines 359-482):
   ```python
   zoom_client = ZoomClient()
   # Multiple Zoom API calls
   ```

3. **Transcript download logic** (Lines 598-650):
   - Direct HTTP calls using `httpx`
   - Access token usage from `zoom_client.access_token`
   - VTT parsing via `zoom_client._parse_vtt()`

**Recommendation**: 
- Inject `ZoomClient` as a dependency
- Move transcript fetching logic to orchestrator or a service layer
- Tools should receive data (transcripts) rather than fetching it themselves

---

### Violation 2: `app/tools/meeting_brief.py`
**Location**: Lines 6, 32-63  
**Issue**: Direct integration with Zoom API  
**Problematic Code Blocks**:

1. **Import** (Line 6):
   ```python
   from app.integrations.zoom_client import ZoomClient
   ```

2. **Direct ZoomClient usage** (Lines 32-63):
   ```python
   zoom_client = ZoomClient()
   # Multiple Zoom API calls for fetching previous meeting transcript
   ```

**Recommendation**: 
- Inject `ZoomClient` as a dependency
- Move transcript fetching to orchestrator layer
- Tool should receive transcript data as input parameter

---

### Violation 3: `app/tools/followup.py`
**Location**: Lines 6, 40-71  
**Issue**: Direct integration with Zoom API  
**Problematic Code Blocks**:

1. **Import** (Line 6):
   ```python
   from app.integrations.zoom_client import ZoomClient
   ```

2. **Direct ZoomClient usage** (Lines 40-71):
   ```python
   zoom_client = ZoomClient()
   # Multiple Zoom API calls for fetching transcript
   ```

**Recommendation**: 
- Inject `ZoomClient` as a dependency
- Move transcript fetching to orchestrator layer
- Tool should receive transcript data as input parameter

---

## Summary of Recommendations

1. **Dependency Injection**: All tools should receive integration clients (`ZoomClient`, `GoogleCalendarClient`, `HubSpotClient`) as constructor parameters rather than creating them directly.

2. **Business Logic Centralization**: Move complex business logic from `tool_execution.py` and `summarization.py` to `orchestrator/agent.py` or dedicated orchestrator modules.

3. **Tool Responsibilities**: Tools should focus on their core functionality (summarization, brief generation, follow-up email generation) and receive data rather than fetching it from external services.

4. **Orchestration Layer**: The orchestrator should handle:
   - Data fetching from integrations
   - Business logic and decision-making
   - Coordination between tools and integrations
   - Message parsing and intent extraction

5. **Integration Abstraction**: Consider creating a service layer that abstracts integration details from tools, allowing tools to work with domain objects rather than API clients.

---

## Files Requiring Changes

1. `app/tools/summarization.py` - Remove Zoom integration, inject dependencies
2. `app/tools/meeting_brief.py` - Remove Zoom integration, inject dependencies
3. `app/tools/followup.py` - Remove Zoom integration, inject dependencies
4. `app/orchestrator/tool_execution.py` - Extract business logic to agent.py or dedicated modules
5. `app/orchestrator/agent.py` - Centralize business logic, handle integration coordination

---

**Report Generated**: 2024-12-19
**Total Violations Found**: 9 (4 integration violations, 2 business logic violations, 3 tool integration violations)

