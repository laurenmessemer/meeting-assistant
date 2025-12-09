# Patch 2: Dry Run Prompt Render

**Date:** 2025-12-08  
**Purpose:** Preview what prompts will look like after memory integration  
**Note:** This shows the actual prompt text that will be sent to the LLM

---

## Test Scenario

**Dummy Memory Data:**
```python
past_context = [
    {
        "key": "interaction",
        "value": "User: Summarize my last MTCA meeting\nAssistant: I've summarized your meeting with MTCA. Key decisions were made about the Q4 budget and project timeline.",
        "extra_data": {"intent": "summarization", "tool_used": "summarization"}
    },
    {
        "key": "interaction",
        "value": "User: Generate a follow-up for Good Health\nAssistant: I've generated a follow-up email for your meeting with Good Health. The email includes action items and next steps.",
        "extra_data": {"intent": "followup", "tool_used": "followup"}
    },
    {
        "key": "project_name",
        "value": "Mesmerize X Good Health project",
        "extra_data": {}
    }
]
```

**Synthesized Insights (from LLM):**
```python
insights = {
    "communication_style": "User prefers concise, action-oriented summaries. Uses specific client names and dates.",
    "client_history": "MTCA meetings frequently discuss budget and timelines. Good Health meetings focus on project deliverables.",
    "recurring_topics": "Budget planning, project timelines, and deliverable tracking appear across multiple meetings.",
    "open_loops": "Q4 budget approval pending from previous MTCA meeting. Good Health project deliverables need follow-up.",
    "preferences": "User prefers professional tone with clear action items and next steps in follow-up emails."
}
```

**Memory Context Section:**
```
Context From Prior Meetings:
- Communication style: User prefers concise, action-oriented summaries. Uses specific client names and dates.
- Client history: MTCA meetings frequently discuss budget and timelines. Good Health meetings focus on project deliverables.
- Recurring themes: Budget planning, project timelines, and deliverable tracking appear across multiple meetings.
- Open loops: Q4 budget approval pending from previous MTCA meeting. Good Health project deliverables need follow-up.
- User preferences: User prefers professional tone with clear action items and next steps in follow-up emails.
```

---

## 1. Summarization Tool - With Transcript

### Input Parameters:
- `transcript`: "John: Let's discuss the Q4 budget... [full transcript]"
- `meeting_title`: "MTCA Q4 Planning Meeting"
- `meeting_date`: "December 8, 2025 at 2:00 PM"
- `recording_date`: "December 8, 2025 at 2:00 PM"
- `attendees`: "John Doe, Jane Smith, Bob Johnson"
- `has_transcript`: `True`
- `past_context`: [dummy data above]

### Generated Prompt:

```
Analyze the following meeting transcript and create a comprehensive, well-structured summary.

Context From Prior Meetings:
- Communication style: User prefers concise, action-oriented summaries. Uses specific client names and dates.
- Client history: MTCA meetings frequently discuss budget and timelines. Good Health meetings focus on project deliverables.
- Recurring themes: Budget planning, project timelines, and deliverable tracking appear across multiple meetings.
- Open loops: Q4 budget approval pending from previous MTCA meeting. Good Health project deliverables need follow-up.
- User preferences: User prefers professional tone with clear action items and next steps in follow-up emails.

Meeting Information:
- Title: MTCA Q4 Planning Meeting
- Calendar Event Date: December 8, 2025 at 2:00 PM
- Zoom Recording Date: December 8, 2025 at 2:00 PM
- Attendees: John Doe, Jane Smith, Bob Johnson

Meeting Transcript:
John: Let's discuss the Q4 budget... [full transcript]

Please create a summary with the following EXACT structure and formatting:

# Meeting Header
MTCA Q4 Planning Meeting

## Date from calendar:
December 8, 2025 at 2:00 PM

## Participants:
John Doe, Jane Smith, Bob Johnson

## Overview:
[Provide a brief 2-3 sentence summary of what the meeting was about, who attended, and the main purpose. Focus on the key objectives and outcomes.]

## Outline:
[Provide 2-3 sentences summarizing the major sections or topics discussed in the meeting. Write in complete sentences (not bullet points) that outline what was covered in each main section. Keep it succinct and focused on the key discussion areas.]

## Conclusion:
[Provide a summary of decisions made, next steps, and any important takeaways. Include any commitments, agreements, or follow-up requirements.]

Format your response using the EXACT section headers shown above (with # and ## markdown formatting). Be clear, concise, and well-organized.
```

**Key Observations:**
- ✅ Memory context appears BEFORE "Meeting Information:" section
- ✅ Markdown structure instructions are UNCHANGED
- ✅ Section headers are PRESERVED
- ✅ Memory context does NOT interfere with structure requirements

---

## 2. Summarization Tool - Without Transcript

### Input Parameters:
- `transcript`: `None`
- `meeting_title`: "Good Health Project Review"
- `meeting_date`: "December 9, 2025 at 10:00 AM"
- `recording_date`: "N/A"
- `attendees`: "Sarah Williams, Mike Chen"
- `has_transcript`: `False`
- `past_context`: [dummy data above]

### Generated Prompt:

```
Create a meeting summary based on the available calendar information. Note that no Zoom recording is available for this meeting.

Context From Prior Meetings:
- Communication style: User prefers concise, action-oriented summaries. Uses specific client names and dates.
- Client history: MTCA meetings frequently discuss budget and timelines. Good Health meetings focus on project deliverables.
- Recurring themes: Budget planning, project timelines, and deliverable tracking appear across multiple meetings.
- Open loops: Q4 budget approval pending from previous MTCA meeting. Good Health project deliverables need follow-up.
- User preferences: User prefers professional tone with clear action items and next steps in follow-up emails.

Meeting Information:
- Title: Good Health Project Review
- Calendar Event Date: December 9, 2025 at 10:00 AM
- Attendees: Sarah Williams, Mike Chen

IMPORTANT: There is no Zoom recording or transcript available for this meeting. Please create a summary with the following EXACT structure and formatting:

# Meeting Header
Good Health Project Review

## Date from calendar:
December 9, 2025 at 10:00 AM

## Participants:
Sarah Williams, Mike Chen

## Overview:
[Provide a brief 2-3 sentence summary based on the meeting title and attendees. Since no transcript is available, focus on what can be inferred from the meeting title and who was scheduled to attend.]

## Recording Status:
⚠️ No Zoom recording is available for this meeting. This summary is based solely on the calendar event information (title, date, and participants).

## Outline:
[Since no transcript is available, you cannot provide details about what was discussed. Instead, write: "No transcript available - unable to provide meeting outline."]

## Conclusion:
[Since no transcript is available, you cannot provide details about decisions or next steps. Instead, write: "No transcript available - unable to provide meeting conclusions."]

Format your response using the EXACT section headers shown above (with # and ## markdown formatting). Be clear, concise, and well-organized.
```

**Key Observations:**
- ✅ Memory context appears BEFORE "Meeting Information:" section
- ✅ Markdown structure instructions are UNCHANGED
- ✅ Section headers are PRESERVED
- ✅ Memory context does NOT interfere with structure requirements

---

## 3. Meeting Brief Tool

### Input Parameters:
- `client_name`: "MTCA"
- `meeting_title`: "Q4 Budget Review"
- `meeting_date`: "December 10, 2025 at 3:00 PM"
- `attendees`: "John Doe, Jane Smith"
- `previous_meeting_summary`: "Previous meeting discussed Q3 budget..."
- `client_context`: "MTCA is a key client with ongoing projects..."
- `past_context`: [dummy data above]

### Generated Prompt:

```
Generate a comprehensive meeting brief to help prepare for an upcoming meeting.

Meeting Information:
Client: MTCA
Meeting Title: Q4 Budget Review
Meeting Date: December 10, 2025 at 3:00 PM
Attendees: John Doe, Jane Smith

Client Context:
MTCA is a key client with ongoing projects...

Previous Meeting Summary:
Previous meeting discussed Q3 budget...

Context From Prior Meetings:
- Communication style: User prefers concise, action-oriented summaries. Uses specific client names and dates.
- Client history: MTCA meetings frequently discuss budget and timelines. Good Health meetings focus on project deliverables.
- Recurring themes: Budget planning, project timelines, and deliverable tracking appear across multiple meetings.
- Open loops: Q4 budget approval pending from previous MTCA meeting. Good Health project deliverables need follow-up.
- User preferences: User prefers professional tone with clear action items and next steps in follow-up emails.

Please create a meeting brief that includes:
1. Key topics to discuss
2. Important context about the client
3. Questions to ask
4. Goals and objectives
5. Any relevant background information

Format the brief in a clear, organized structure that will help prepare for the meeting.
```

**Key Observations:**
- ✅ Memory context added to `context_parts` list
- ✅ Appears in "Meeting Information:" section (safe - free-form output)
- ✅ No structure constraints (low risk)
- ✅ Memory context provides additional context for brief generation

---

## 4. Follow-up Tool

### Input Parameters:
- `meeting_summary`: "Meeting discussed Q4 budget and project timelines..."
- `transcript`: `None`
- `meeting_title`: "MTCA Q4 Planning Meeting"
- `meeting_date`: "December 8, 2025 at 2:00 PM"
- `client_name`: "MTCA"
- `client_email`: "contact@mtca.com"
- `attendees`: "John Doe, Jane Smith, Bob Johnson"
- `action_items`: ["Review budget proposal", "Schedule follow-up meeting"]
- `decisions`: [{"description": "Approve Q4 budget", "context": "Pending final review"}]
- `past_context`: [dummy data above]

### Generated Prompt:

```
Generate a professional follow-up email based on the meeting information below.

Context From Prior Meetings:
- Communication style: User prefers concise, action-oriented summaries. Uses specific client names and dates.
- Client history: MTCA meetings frequently discuss budget and timelines. Good Health meetings focus on project deliverables.
- Recurring themes: Budget planning, project timelines, and deliverable tracking appear across multiple meetings.
- Open loops: Q4 budget approval pending from previous MTCA meeting. Good Health project deliverables need follow-up.
- User preferences: User prefers professional tone with clear action items and next steps in follow-up emails.

Meeting Information:
- Title: MTCA Q4 Planning Meeting
- Date: December 8, 2025 at 2:00 PM
- Client: MTCA
- Attendees: John Doe, Jane Smith, Bob Johnson

Meeting Summary:
Meeting discussed Q4 budget and project timelines...

Decisions Made:
• Approve Q4 budget (Context: Pending final review)

Action Items & Next Steps:
• Review budget proposal
• Schedule follow-up meeting

Please create a follow-up email that:
1. Opens with a warm thank you for the client's time
2. Briefly summarizes the key points discussed (2-3 sentences)
3. Clearly lists action items and next steps, indicating who is responsible for each
4. Confirms any decisions that were made
5. Sets clear expectations for follow-up communication or next meeting

The email should be:
- Professional and warm in tone
- Clear and concise
- Actionable with specific next steps
- Appropriate for the client relationship

Respond in JSON format:
{
    "subject": "Email subject line",
    "body": "Email body text (use proper email formatting with paragraphs)"
}
```

**Key Observations:**
- ✅ Memory context appears BEFORE "Meeting Information:" section
- ✅ JSON structure instructions are UNCHANGED
- ✅ JSON keys (`subject`, `body`) are PRESERVED
- ✅ Memory context does NOT interfere with JSON format requirements

---

## 5. Edge Case: Empty Memory

### Scenario: `past_context = None` or `past_context = []`

### Generated Prompt (Summarization with transcript):

```
Analyze the following meeting transcript and create a comprehensive, well-structured summary.

Meeting Information:
- Title: MTCA Q4 Planning Meeting
- Calendar Event Date: December 8, 2025 at 2:00 PM
- Zoom Recording Date: December 8, 2025 at 2:00 PM
- Attendees: John Doe, Jane Smith, Bob Johnson

Meeting Transcript:
John: Let's discuss the Q4 budget... [full transcript]

Please create a summary with the following EXACT structure and formatting:

# Meeting Header
MTCA Q4 Planning Meeting

## Date from calendar:
December 8, 2025 at 2:00 PM

## Participants:
John Doe, Jane Smith, Bob Johnson

## Overview:
[Provide a brief 2-3 sentence summary of what the meeting was about, who attended, and the main purpose. Focus on the key objectives and outcomes.]

## Outline:
[Provide 2-3 sentences summarizing the major sections or topics discussed in the meeting. Write in complete sentences (not bullet points) that outline what was covered in each main section. Keep it succinct and focused on the key discussion areas.]

## Conclusion:
[Provide a summary of decisions made, next steps, and any important takeaways. Include any commitments, agreements, or follow-up requirements.]

Format your response using the EXACT section headers shown above (with # and ## markdown formatting). Be clear, concise, and well-organized.
```

**Key Observations:**
- ✅ No memory context section appears (empty string)
- ✅ Prompt is identical to original (backward compatible)
- ✅ No errors or exceptions thrown

---

## 6. Edge Case: Partial Insights (Some Fields Empty)

### Scenario: LLM returns partial insights
```python
insights = {
    "communication_style": "User prefers concise summaries",
    "client_history": "",  # Empty
    "recurring_topics": "Budget planning",
    "open_loops": "",  # Empty
    "preferences": ""  # Empty
}
```

### Generated Memory Context Section:

```
Context From Prior Meetings:
- Communication style: User prefers concise summaries
- Client history: 
- Recurring themes: Budget planning
- Open loops: 
- User preferences: 
```

**Note:** Since `any(insights.values())` returns `True` (at least one field has content), the section is included. Empty fields are shown as empty strings.

**Alternative:** We could filter out empty fields, but the current implementation is safer (shows all fields, even if empty).

---

## 7. Character Limit Enforcement

### Scenario: Memory context section exceeds 1200 characters

**Before Truncation:**
```
Context From Prior Meetings:
- Communication style: [very long text... 500 chars]
- Client history: [very long text... 500 chars]
- Recurring themes: [very long text... 500 chars]
- Open loops: [very long text... 500 chars]
- User preferences: [very long text... 500 chars]
```
**Total:** ~2500 characters

**After Truncation:**
```
Context From Prior Meetings:
- Communication style: [truncated to fit 1200 char limit...]
```

**Key Observations:**
- ✅ 1200 character limit enforced
- ✅ Truncation happens at section level (not per field)
- ✅ Section is still included (even if truncated)

---

## 8. Safety Validation

### ✅ Summarization Tool:
- Memory context BEFORE "Meeting Information:" ✅
- Markdown structure instructions UNCHANGED ✅
- Section headers PRESERVED ✅
- No injection in decision extraction prompt ✅

### ✅ Meeting Brief Tool:
- Memory context in `context_parts` list ✅
- Free-form output (no constraints) ✅
- No structure requirements ✅

### ✅ Follow-up Tool:
- Memory context BEFORE "Meeting Information:" ✅
- JSON structure instructions UNCHANGED ✅
- JSON keys PRESERVED ✅
- No injection in JSON format section ✅

---

## 9. Backward Compatibility Check

### Scenario: Tools called WITHOUT `past_context` parameter

**Result:**
- ✅ `past_context = None` → `insights` = all empty strings
- ✅ `any(insights.values())` = `False` → `memory_context_section = ""`
- ✅ Prompt is identical to original (no memory section)
- ✅ No errors thrown
- ✅ All existing functionality preserved

---

## 10. Summary

**All Prompts:**
- ✅ Memory context injected in safe locations
- ✅ Structure instructions preserved
- ✅ Formatting requirements maintained
- ✅ Backward compatible (works without memory)
- ✅ Graceful error handling (continues without memory on failure)
- ✅ Character limits enforced (1200 chars max)

**Ready for Implementation:** ✅ **YES** - All safety requirements met.

