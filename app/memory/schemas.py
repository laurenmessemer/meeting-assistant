"""Pydantic schemas for API requests and responses."""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, EmailStr


# User Schemas
class UserBase(BaseModel):
    email: EmailStr
    name: Optional[str] = None


class UserCreate(UserBase):
    pass


class UserResponse(UserBase):
    id: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


# Client Schemas
class ClientBase(BaseModel):
    hubspot_id: str
    name: str
    email: Optional[str] = None
    company: Optional[str] = None
    extra_data: Optional[Dict[str, Any]] = None


class ClientCreate(ClientBase):
    user_id: int


class ClientResponse(ClientBase):
    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


# Meeting Schemas
class MeetingBase(BaseModel):
    title: str
    scheduled_time: datetime
    duration_minutes: Optional[int] = None
    attendees: Optional[List[str]] = None
    calendar_event_id: Optional[str] = None
    zoom_meeting_id: Optional[str] = None


class MeetingCreate(MeetingBase):
    user_id: int
    client_id: Optional[int] = None


class MeetingUpdate(BaseModel):
    status: Optional[str] = None
    transcript: Optional[str] = None
    recording_url: Optional[str] = None
    summary: Optional[str] = None


class MeetingResponse(MeetingBase):
    id: int
    user_id: int
    client_id: Optional[int] = None
    status: str
    transcript: Optional[str] = None
    recording_url: Optional[str] = None
    summary: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


# Decision Schemas
class DecisionBase(BaseModel):
    description: str
    context: Optional[str] = None


class DecisionCreate(DecisionBase):
    meeting_id: Optional[int] = None
    client_id: int


class DecisionResponse(DecisionBase):
    id: int
    meeting_id: Optional[int] = None
    client_id: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


# Action Schemas
class ActionBase(BaseModel):
    description: str
    assignee: Optional[str] = None
    due_date: Optional[datetime] = None
    status: Optional[str] = "pending"


class ActionCreate(ActionBase):
    meeting_id: Optional[int] = None
    client_id: int


class ActionResponse(ActionBase):
    id: int
    meeting_id: Optional[int] = None
    client_id: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


# Memory Entry Schemas
class MemoryEntryBase(BaseModel):
    key: str
    value: str
    extra_data: Optional[Dict[str, Any]] = None


class MemoryEntryCreate(MemoryEntryBase):
    user_id: int
    client_id: Optional[int] = None


class MemoryEntryResponse(MemoryEntryBase):
    id: int
    user_id: int
    client_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


# Chat Schemas
class ChatMessage(BaseModel):
    message: str
    user_id: Optional[int] = None
    client_id: Optional[int] = None


class ChatResponse(BaseModel):
    response: str
    tool_used: Optional[str] = None
    extra_data: Optional[Dict[str, Any]] = None

