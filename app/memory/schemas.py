"""Pydantic schemas for memory and database models."""

from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime


class MemoryEntryCreate(BaseModel):
    """Schema for creating a memory entry."""
    user_id: int
    client_id: Optional[int] = None
    key: str
    value: str
    extra_data: Optional[Dict[str, Any]] = None


class DecisionCreate(BaseModel):
    """Schema for creating a decision."""
    meeting_id: int
    client_id: int
    description: str
    context: Optional[str] = None


class ActionCreate(BaseModel):
    """Schema for creating an action item."""
    meeting_id: int
    client_id: int
    description: str
    assignee: Optional[str] = None
    due_date: Optional[datetime] = None


class MeetingCreate(BaseModel):
    """Schema for creating a meeting."""
    user_id: int
    client_id: Optional[int] = None
    calendar_event_id: Optional[str] = None
    zoom_meeting_id: Optional[str] = None
    title: str
    scheduled_time: datetime
    transcript: Optional[str] = None
    status: Optional[str] = "scheduled"
    attendees: Optional[List[str]] = None


class MeetingUpdate(BaseModel):
    """Schema for updating a meeting."""
    summary: Optional[str] = None
    transcript: Optional[str] = None
    status: Optional[str] = None


class MeetingOption(BaseModel):
    """Schema for meeting selection options."""
    id: str
    title: str
    date: str
    calendar_event_id: Optional[str] = None
    meeting_id: Optional[int] = None
    client_name: Optional[str] = None

