# Tool Layer Memory Integration Audit

**Date:** 2025-12-08  
**Scope:** Zero-change audit of tool layer for memory integration  
**Purpose:** Identify safe injection points and formatting requirements

---

## 1. Exact Function Signatures

### 1.1 `summarize_meeting()`

**Location:** `app/tools/summarization.py:14-22`

**Current Signature:**
```python
async def summarize_meeting(
    self,
    transcript: Optional[str] = None,
    meeting_title: Optional[str] = None,
    meeting_date: Optional[str] = None,
    recording_date: Optional[str] = None,
    attendees: Optional[str] = None,
    has_transcript: bool = True
) -> Dict[str, Any]:
```

**Return Type:** `Dict[str, Any]` with keys:
- `summary`: str (markdown-formatted text)
- `meeting_title`: str
- `meeting_date`: str
- `recording_date`: str
- `attendees`: str
- `decisions`: List[Dict[str, str]]
- `has_transcript`: bool

---

### 1.2 `generate_brief()`

**Location:** `app/tools/meeting_brief.py:14-22`

**Current Signature:**
```python
async def generate_brief(
    self,
    client_name: Optional[str] = None,
    meeting_title: Optional[str] = None,
    meeting_date: Optional[str] = None,
    attendees: Optional[str] = None,
    previous_meeting_summary: Optional[str] = None,
    client_context: Optional[str] = None
) -> Dict[str, Any]:
```

**Return Type:** `Dict[str, Any]` with keys:
- `brief`: str (free-form text)
- `client_name`: Optional[str]
- `meeting_title`: Optional[str]
- `meeting_date`: Optional[str]
- `attendees`: Optional[str]

**Note:** Already has `previous_meeting_summary` parameter (line 20) - this is similar to what we want to add.

---

### 1.3 `generate_followup()`

**Location:** `app/tools/followup.py:14-25`

**Current Signature:**
```python
async def generate_followup(
    self,
    meeting_summary: Optional[str] = None,
    transcript: Optional[str] = None,
    meeting_title: Optional[str] = None,
    meeting_date: Optional[str] = None,
    client_name: Optional[str] = None,
    client_email: Optional[str] = None,
    attendees: Optional[str] = None,
    action_items: Optional[list] = None,
    decisions: Optional[list] = None
) -> Dict[str, Any]:
```

**Return Type:** `Dict[str, Any]` with keys:
- `subject`: str
- `body`: str
- `client_name`: Optional[str]
- `client_email`: Optional[str]

---

## 2. LLM Prompt Construction Locations

### 2.1 `summarize_meeting()` - Prompt Locations

**Primary Prompt (No Transcript):** Lines 52-82
- **Location:** Inside `if not has_transcript:` block
- **Purpose:** Generate summary from calendar info only
- **Structure:** Multi-line f-string with exact markdown formatting instructions
- **Critical:** Contains EXACT markdown structure requirements (# Meeting Header, ## Date from calendar, etc.)

**Primary Prompt (With Transcript):** Lines 85-116
- **Location:** Inside `else:` block (when `has_transcript=True`)
- **Purpose:** Generate summary from transcript
- **Structure:** Multi-line f-string with exact markdown formatting instructions
- **Critical:** Contains EXACT markdown structure requirements

**Decision Extraction Prompt:** Lines 128-139
- **Location:** Inside `if has_transcript:` block (after summary generation)
- **Purpose:** Extract decisions from generated summary
- **Structure:** JSON extraction prompt
- **Critical:** Uses `summary_text` from previous LLM call

**LLM Call Locations:**
- Line 118-123: Primary summary generation
- Line 141-145: Decision extraction (only if `has_transcript=True`)

---

### 2.2 `generate_brief()` - Prompt Construction

**Prompt Location:** Lines 53-65
- **Location:** After building `context_parts` list (lines 38-51)
- **Purpose:** Generate meeting brief
- **Structure:** Single multi-line f-string
- **Context Building:** Uses `context_parts` list that includes:
  - `client_name`
  - `meeting_title`
  - `meeting_date`
  - `attendees`
  - `client_context` (if provided)
  - `previous_meeting_summary` (if provided)

**LLM Call Location:**
- Line 67-72: Single LLM call for brief generation

---

### 2.3 `generate_followup()` - Prompt Construction

**Prompt Location:** Lines 95-126
- **Location:** After formatting decisions and action items (lines 55-92)
- **Purpose:** Generate follow-up email
- **Structure:** Single multi-line f-string with conditional sections
- **Context Building:** Includes:
  - `meeting_info_parts` (title, date, client, attendees)
  - `meeting_summary`
  - `transcript` (if provided)
  - `decisions_text` (formatted)
  - `action_items_text` (formatted)

**LLM Call Location:**
- Line 128-133: Single LLM call for email generation (JSON response)

---

## 3. UI Formatting Requirements

### 3.1 Summarization Tool Output Formatting

**UI Parser:** `formatStructuredSummary()` in `ui_router.py:593-676`

**Expected Format:**
- **Header:** `# Meeting Header` followed by title
- **Sections:** `## Section Title:` followed by content
- **Required Sections:**
  - `## Date from calendar:`
  - `## Participants:`
  - `## Overview:`
  - `## Outline:`
  - `## Conclusion:`

**Critical Requirements:**
- ✅ **MUST preserve exact markdown headers** (`#` and `##`)
- ✅ **MUST preserve section structure** (UI parses by headers)
- ✅ **MUST NOT inject memory into section content** (would break UI parsing)
- ✅ **MUST NOT modify section titles** (UI expects exact titles)

**UI Parsing Logic:**
- Line 595: Checks for `#` or `##` to detect structured summary
- Lines 620-658: Parses by `##` headers to create sections
- Line 652: Extracts section title from `## Title:` format
- Line 635: Creates `summary-section-content` divs for each section

**Risk:** 🔴 **HIGH** - If markdown structure changes, UI parsing will break.

---

### 3.2 Meeting Brief Tool Output Formatting

**UI Parser:** No specific parser - free-form text

**Expected Format:**
- Free-form text with no specific structure requirements
- UI displays as plain text in assistant card

**Critical Requirements:**
- ✅ **No markdown structure required**
- ✅ **Can inject memory anywhere in prompt** (no UI parsing dependencies)
- ✅ **Output is free-form** (no formatting constraints)

**Risk:** 🟢 **LOW** - No structured formatting requirements.

---

### 3.3 Follow-up Tool Output Formatting

**UI Parser:** `formatFollowupEmail()` in `ui_router.py:678-748`

**Expected Format:**
- **JSON structure:** `{"subject": str, "body": str}`
- **Body:** Plain text with paragraphs (split by `\n\n`)
- **Subject:** Displayed as `<h2>` with class `followup-subject`
- **Body:** Displayed as paragraphs in `followup-body` div

**Critical Requirements:**
- ✅ **MUST return JSON** (not markdown)
- ✅ **MUST preserve JSON structure** (`subject` and `body` keys)
- ✅ **Body can be free-form text** (no markdown required)
- ✅ **Can inject memory into prompt** (output is JSON, not markdown)

**UI Parsing Logic:**
- Line 693: Checks for `subject` and `body` keys
- Line 702-705: Creates `<h2>` for subject
- Line 714: Splits body by `\n\n` into paragraphs
- Line 720: Handles markdown-like formatting in body (but not required)

**Risk:** 🟡 **MEDIUM** - JSON structure must be preserved, but body content is flexible.

---

## 4. Safe Memory Injection Points

### 4.1 Where We CAN Safely Inject `past_context`

#### **Summarization Tool:**

**✅ SAFE: Before "Meeting Information" section (Line 85-91)**
- **Location:** In the "with transcript" prompt, before "Meeting Information:"
- **Reason:** Context section, not part of output structure
- **Format:** Add as a separate section before meeting info
- **Example:**
  ```python
  prompt = f"""Analyze the following meeting transcript and create a comprehensive, well-structured summary.
  
  {past_context_section if past_context else ""}
  
  Meeting Information:
  - Title: {title}
  ...
  ```

**✅ SAFE: Before "Meeting Information" section (Line 52-57)**
- **Location:** In the "no transcript" prompt, before "Meeting Information:"
- **Reason:** Context section, not part of output structure
- **Format:** Add as a separate section before meeting info

**❌ MUST NOT: In decision extraction prompt (Line 128-139)**
- **Reason:** This prompt extracts decisions from the summary, not generates new content
- **Risk:** Would contaminate decision extraction logic

---

#### **Meeting Brief Tool:**

**✅ SAFE: In `context_parts` list (Line 38-51)**
- **Location:** Add to `context_parts` list before prompt construction
- **Reason:** Already has `previous_meeting_summary` - same pattern
- **Format:** Add as new item in `context_parts` list
- **Example:**
  ```python
  if past_context:
      context_parts.append(f"\nPrevious Conversations:\n{formatted_past_context}")
  ```

**✅ SAFE: Anywhere in prompt (Line 53-65)**
- **Reason:** Free-form output, no structure requirements
- **Format:** Can be added anywhere in the prompt

---

#### **Follow-up Tool:**

**✅ SAFE: Before "Meeting Information" section (Line 95-98)**
- **Location:** Before "Meeting Information:" in prompt
- **Reason:** Context section, not part of JSON output structure
- **Format:** Add as a separate section before meeting info
- **Example:**
  ```python
  prompt = f"""Generate a professional follow-up email based on the meeting information below.
  
  {past_context_section if past_context else ""}
  
  Meeting Information:
  {chr(10).join(meeting_info_parts) if meeting_info_parts else "No meeting information provided."}
  ...
  ```

**✅ SAFE: After "Meeting Summary" section (Line 100-101)**
- **Location:** After meeting summary, before transcript
- **Reason:** Additional context, doesn't affect JSON structure
- **Format:** Add as optional section

---

### 4.2 Where We MUST NOT Inject `past_context`

#### **Summarization Tool:**

**❌ MUST NOT: In markdown structure instructions (Lines 59-82, 96-115)**
- **Reason:** These instructions define the EXACT output format that UI parses
- **Risk:** Would break UI parsing if structure changes
- **Example of FORBIDDEN:**
  ```python
  # ❌ DO NOT DO THIS:
  prompt = f"""...
  Please create a summary with the following EXACT structure:
  {past_context}  # ← FORBIDDEN - breaks structure instructions
  # Meeting Header
  ...
  ```

**❌ MUST NOT: In decision extraction prompt (Lines 128-139)**
- **Reason:** This prompt extracts decisions from summary, not generates content
- **Risk:** Would contaminate decision extraction

**❌ MUST NOT: In section content placeholders (Lines 71, 77, 80, 108, 111, 114)**
- **Reason:** These are instructions for LLM, not context
- **Risk:** Would confuse LLM about what to generate

---

#### **Meeting Brief Tool:**

**✅ NO RESTRICTIONS** - Free-form output, can inject anywhere safely

---

#### **Follow-up Tool:**

**❌ MUST NOT: In JSON structure instructions (Lines 122-126)**
- **Reason:** These define the exact JSON format required
- **Risk:** Would break JSON parsing if structure changes
- **Example of FORBIDDEN:**
  ```python
  # ❌ DO NOT DO THIS:
  prompt = f"""...
  {past_context}  # ← FORBIDDEN if placed here
  Respond in JSON format:
  {{
      "subject": "...",
      "body": "..."
  }}"""
  ```

**❌ MUST NOT: In JSON response format section (Lines 122-126)**
- **Reason:** Must preserve exact JSON structure
- **Risk:** Would break JSON parsing

---

### 4.3 UI Formatting Preservation Requirements

#### **Summarization Tool:**

**MUST PRESERVE:**
- ✅ Exact markdown headers (`# Meeting Header`, `## Section Title:`)
- ✅ Exact section titles (`Date from calendar:`, `Participants:`, `Overview:`, `Outline:`, `Conclusion:`)
- ✅ Section structure (UI parses by `##` headers)
- ✅ Markdown formatting in section content (UI preserves markdown)

**CAN MODIFY:**
- ✅ Section content (what goes inside each section)
- ✅ Add new sections (if UI can handle them)

**CANNOT MODIFY:**
- ❌ Section header format (`## Title:`)
- ❌ Required section titles
- ❌ Overall markdown structure

---

#### **Meeting Brief Tool:**

**MUST PRESERVE:**
- ✅ Nothing specific (free-form output)

**CAN MODIFY:**
- ✅ Everything (no formatting constraints)

---

#### **Follow-up Tool:**

**MUST PRESERVE:**
- ✅ JSON structure (`{"subject": str, "body": str}`)
- ✅ JSON keys (`subject`, `body`)

**CAN MODIFY:**
- ✅ Body content (free-form text)
- ✅ Subject content (free-form text)

**CANNOT MODIFY:**
- ❌ JSON structure
- ❌ JSON keys

---

### 4.4 Memory Output Change Risks

#### **Summarization Tool:**

**Risk:** 🔴 **HIGH** - If memory is injected incorrectly, it could:
1. Break markdown structure → UI parsing fails
2. Modify section titles → UI can't find sections
3. Add unexpected sections → UI displays incorrectly

**Mitigation:**
- ✅ Inject memory BEFORE structure instructions
- ✅ Keep memory in separate context section
- ✅ Do NOT modify structure instructions
- ✅ Do NOT inject into section content placeholders

---

#### **Meeting Brief Tool:**

**Risk:** 🟢 **LOW** - Free-form output, no structure requirements

**Mitigation:**
- ✅ Can inject anywhere safely
- ✅ No special handling needed

---

#### **Follow-up Tool:**

**Risk:** 🟡 **MEDIUM** - If memory is injected incorrectly, it could:
1. Break JSON structure → JSON parsing fails
2. Modify JSON keys → UI can't find `subject`/`body`

**Mitigation:**
- ✅ Inject memory BEFORE JSON structure instructions
- ✅ Keep memory in separate context section
- ✅ Do NOT modify JSON structure instructions
- ✅ Do NOT inject into JSON format section

---

## 5. Diff Preview (No Modifications)

### 5.1 `summarization.py` - Proposed Changes

```diff
--- a/app/tools/summarization.py
+++ b/app/tools/summarization.py
@@ -14,6 +14,7 @@ class SummarizationTool:
     async def summarize_meeting(
         self,
         transcript: Optional[str] = None,
         meeting_title: Optional[str] = None,
         meeting_date: Optional[str] = None,
         recording_date: Optional[str] = None,
         attendees: Optional[str] = None,
-        has_transcript: bool = True
+        has_transcript: bool = True,
+        past_context: Optional[List[Dict[str, Any]]] = None
     ) -> Dict[str, Any]:
         """
         Summarize a meeting and extract decisions/actions.
@@ -26,6 +27,7 @@ class SummarizationTool:
             recording_date: Zoom recording date for display
             attendees: Comma-separated list of attendee names
             has_transcript: Whether transcript is available (default: True)
+            past_context: Optional list of past meeting memories for context
         
         Returns:
             Dictionary with summary, decisions, and metadata
@@ -48,6 +50,20 @@ class SummarizationTool:
         title = meeting_title or "Untitled Meeting"
         date_str = meeting_date or "Unknown date"
         recording_date_str = recording_date or "N/A"
         attendees_display = attendees or "Not specified"
         
+        # Build past context section if provided
+        past_context_section = ""
+        if past_context:
+            past_context_lines = []
+            for mem in past_context:
+                value = mem.get("value", "")
+                # Sanitize: truncate long memories to prevent prompt bloat
+                if len(value) > 500:
+                    value = value[:500] + "..."
+                past_context_lines.append(f"- {value}")
+            if past_context_lines:
+                past_context_section = f"\n\nPrevious Meeting Context:\n{chr(10).join(past_context_lines)}\n"
         
         # Generate structured summary using LLM
         if not has_transcript:
             # Generate summary without transcript - just calendar information
-            prompt = f"""Create a meeting summary based on the available calendar information. Note that no Zoom recording is available for this meeting.
+            prompt = f"""Create a meeting summary based on the available calendar information. Note that no Zoom recording is available for this meeting.
+{past_context_section}
 
 Meeting Information:
 - Title: {title}
@@ -82,7 +98,7 @@ class SummarizationTool:
 Format your response using the EXACT section headers shown above (with # and ## markdown formatting). Be clear, concise, and well-organized."""
         else:
             # Generate summary with transcript
-            prompt = f"""Analyze the following meeting transcript and create a comprehensive, well-structured summary.
+            prompt = f"""Analyze the following meeting transcript and create a comprehensive, well-structured summary.
+{past_context_section}
 
 Meeting Information:
 - Title: {title}
```

**Key Points:**
- ✅ Adds optional `past_context` parameter
- ✅ Builds `past_context_section` BEFORE structure instructions
- ✅ Injects memory BEFORE "Meeting Information:" section
- ✅ Does NOT modify markdown structure instructions
- ✅ Does NOT modify decision extraction prompt
- ✅ Sanitizes memory (truncates to 500 chars)

---

### 5.2 `meeting_brief.py` - Proposed Changes

```diff
--- a/app/tools/meeting_brief.py
+++ b/app/tools/meeting_brief.py
@@ -14,6 +14,7 @@ class MeetingBriefTool:
     async def generate_brief(
         self,
         client_name: Optional[str] = None,
         meeting_title: Optional[str] = None,
         meeting_date: Optional[str] = None,
         attendees: Optional[str] = None,
         previous_meeting_summary: Optional[str] = None,
-        client_context: Optional[str] = None
+        client_context: Optional[str] = None,
+        past_context: Optional[List[Dict[str, Any]]] = None
     ) -> Dict[str, Any]:
         """
         Generate a meeting brief.
@@ -25,6 +26,7 @@ class MeetingBriefTool:
             attendees: Comma-separated list of attendees
             previous_meeting_summary: Optional summary of previous meeting for context
             client_context: Optional client context/information
+            past_context: Optional list of past meeting memories for context
         
         Returns:
             Dictionary with brief content
@@ -48,6 +50,18 @@ class MeetingBriefTool:
         if previous_meeting_summary:
             context_parts.append(f"\nPrevious Meeting Summary:\n{previous_meeting_summary}")
         
+        # Add past context if provided
+        if past_context:
+            past_context_lines = []
+            for mem in past_context:
+                value = mem.get("value", "")
+                # Sanitize: truncate long memories to prevent prompt bloat
+                if len(value) > 500:
+                    value = value[:500] + "..."
+                past_context_lines.append(f"- {value}")
+            if past_context_lines:
+                context_parts.append(f"\nPrevious Conversations:\n{chr(10).join(past_context_lines)}")
+        
         prompt = f"""Generate a comprehensive meeting brief to help prepare for an upcoming meeting.
 
 Meeting Information:
```

**Key Points:**
- ✅ Adds optional `past_context` parameter
- ✅ Adds to existing `context_parts` list (same pattern as `previous_meeting_summary`)
- ✅ Injects memory into prompt via `context_parts`
- ✅ No structure constraints (free-form output)
- ✅ Sanitizes memory (truncates to 500 chars)

---

### 5.3 `followup.py` - Proposed Changes

```diff
--- a/app/tools/followup.py
+++ b/app/tools/followup.py
@@ -14,6 +14,7 @@ class FollowUpTool:
     async def generate_followup(
         self,
         meeting_summary: Optional[str] = None,
         transcript: Optional[str] = None,
         meeting_title: Optional[str] = None,
         meeting_date: Optional[str] = None,
         client_name: Optional[str] = None,
         client_email: Optional[str] = None,
         attendees: Optional[str] = None,
-        action_items: Optional[list] = None,
-        decisions: Optional[list] = None
+        action_items: Optional[list] = None,
+        decisions: Optional[list] = None,
+        past_context: Optional[List[Dict[str, Any]]] = None
     ) -> Dict[str, Any]:
         """
         Generate a follow-up email.
@@ -35,6 +36,7 @@ class FollowUpTool:
             attendees: Attendees list as formatted string
             action_items: List of action items from the meeting
             decisions: List of decisions made in the meeting (can be dicts with description/context)
+            past_context: Optional list of past meeting memories for context
         
         Returns:
             Dictionary with email subject and body
@@ -92,6 +94,18 @@ class FollowUpTool:
                 # Action items are simple strings
                 action_items_text = "\n".join([f"• {item}" for item in action_items])
         
+        # Build past context section if provided
+        past_context_section = ""
+        if past_context:
+            past_context_lines = []
+            for mem in past_context:
+                value = mem.get("value", "")
+                # Sanitize: truncate long memories to prevent prompt bloat
+                if len(value) > 500:
+                    value = value[:500] + "..."
+                past_context_lines.append(f"- {value}")
+            if past_context_lines:
+                past_context_section = f"\n\nPrevious Conversations:\n{chr(10).join(past_context_lines)}\n"
+        
         # Build comprehensive prompt similar to summarization style
-        prompt = f"""Generate a professional follow-up email based on the meeting information below.
+        prompt = f"""Generate a professional follow-up email based on the meeting information below.
+{past_context_section}
 
 Meeting Information:
 {chr(10).join(meeting_info_parts) if meeting_info_parts else "No meeting information provided."}
```

**Key Points:**
- ✅ Adds optional `past_context` parameter
- ✅ Builds `past_context_section` BEFORE "Meeting Information:" section
- ✅ Injects memory BEFORE JSON structure instructions
- ✅ Does NOT modify JSON structure instructions
- ✅ Sanitizes memory (truncates to 500 chars)

---

## 6. Summary of Safe Injection Points

### 6.1 Summarization Tool

**✅ SAFE Injection Points:**
1. **Before "Meeting Information:" in no-transcript prompt** (Line 52)
2. **Before "Meeting Information:" in with-transcript prompt** (Line 85)

**❌ FORBIDDEN Injection Points:**
1. **In markdown structure instructions** (Lines 59-82, 96-115)
2. **In decision extraction prompt** (Lines 128-139)
3. **In section content placeholders** (Lines 71, 77, 80, 108, 111, 114)

**Formatting Requirements:**
- ✅ Must preserve exact markdown headers
- ✅ Must preserve section titles
- ✅ Must preserve section structure

---

### 6.2 Meeting Brief Tool

**✅ SAFE Injection Points:**
1. **In `context_parts` list** (Line 38-51) - **RECOMMENDED**
2. **Anywhere in prompt** (Line 53-65) - No restrictions

**❌ FORBIDDEN Injection Points:**
- None (free-form output)

**Formatting Requirements:**
- ✅ None (free-form output)

---

### 6.3 Follow-up Tool

**✅ SAFE Injection Points:**
1. **Before "Meeting Information:" section** (Line 95) - **RECOMMENDED**
2. **After "Meeting Summary:" section** (Line 100) - Alternative

**❌ FORBIDDEN Injection Points:**
1. **In JSON structure instructions** (Lines 122-126)
2. **In JSON response format section** (Lines 122-126)

**Formatting Requirements:**
- ✅ Must preserve JSON structure
- ✅ Must preserve JSON keys (`subject`, `body`)

---

## 7. Memory Sanitization Requirements

**All Tools Must:**
1. ✅ **Truncate long memories** (max 500 chars per memory)
2. ✅ **Limit number of memories** (max 5 items - already done in Patch 1)
3. ✅ **Handle None/empty gracefully** (optional parameter with `None` default)
4. ✅ **Extract `value` field safely** (use `.get("value", "")`)

**Sanitization Pattern (All Tools):**
```python
if past_context:
    past_context_lines = []
    for mem in past_context:
        value = mem.get("value", "")
        # Sanitize: truncate long memories to prevent prompt bloat
        if len(value) > 500:
            value = value[:500] + "..."
        past_context_lines.append(f"- {value}")
    if past_context_lines:
        past_context_section = f"\n\nPrevious Conversations:\n{chr(10).join(past_context_lines)}\n"
```

---

## 8. Validation Checklist

### 8.1 Function Signatures
- ✅ `summarize_meeting()` - Add `past_context: Optional[List[Dict[str, Any]]] = None`
- ✅ `generate_brief()` - Add `past_context: Optional[List[Dict[str, Any]]] = None`
- ✅ `generate_followup()` - Add `past_context: Optional[List[Dict[str, Any]]] = None`

### 8.2 Prompt Construction
- ✅ Summarization: Inject BEFORE "Meeting Information:" section
- ✅ Meeting Brief: Add to `context_parts` list
- ✅ Follow-up: Inject BEFORE "Meeting Information:" section

### 8.3 Formatting Preservation
- ✅ Summarization: Preserve markdown structure, section titles, headers
- ✅ Meeting Brief: No constraints (free-form)
- ✅ Follow-up: Preserve JSON structure and keys

### 8.4 Safety Measures
- ✅ All parameters optional with `None` defaults
- ✅ Memory sanitization (truncate to 500 chars)
- ✅ Graceful handling of empty/None memory
- ✅ No modification of structure instructions
- ✅ No modification of JSON format instructions

### 8.5 No Breaking Changes
- ✅ Backward-compatible (optional parameters)
- ✅ No business logic moved outside tools
- ✅ No duplicated logic
- ✅ No broken formatting
- ✅ No architectural violations

---

## 9. Risk Assessment

**Overall Risk:** 🟢 **LOW**

**Risks Identified:**
1. 🔴 **Summarization:** High risk if markdown structure is modified
2. 🟡 **Follow-up:** Medium risk if JSON structure is modified
3. 🟢 **Meeting Brief:** Low risk (free-form output)

**Mitigations:**
- ✅ All injection points are BEFORE structure instructions
- ✅ Memory sanitization prevents prompt bloat
- ✅ Optional parameters ensure backward compatibility
- ✅ No modification of critical formatting sections

---

## 10. Conclusion

**Audit Status:** ✅ **COMPLETE**

**Findings:**
- ✅ All function signatures identified
- ✅ All prompt construction locations identified
- ✅ All UI formatting requirements identified
- ✅ Safe injection points identified
- ✅ Forbidden injection points identified
- ✅ Diff preview generated

**Recommendation:** ✅ **SAFE TO PROCEED** - All changes are isolated, optional, and preserve formatting requirements.

**Next Steps:**
1. Apply Patch 2 with memory integration to all three tools
2. Test UI formatting preservation
3. Test with empty/None memory
4. Test with various memory sizes

