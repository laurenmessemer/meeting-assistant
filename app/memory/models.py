"""SQLAlchemy database models."""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON, Boolean
from sqlalchemy.orm import relationship
from app.db.session import Base


class User(Base):
    """User model."""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    clients = relationship("Client", back_populates="user")
    meetings = relationship("Meeting", back_populates="user")


class Client(Base):
    """Client model (from HubSpot)."""
    __tablename__ = "clients"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    hubspot_id = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=False)
    email = Column(String, nullable=True)
    company = Column(String, nullable=True)
    extra_data = Column(JSON, default=dict)  # Store additional HubSpot data
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="clients")
    meetings = relationship("Meeting", back_populates="client")
    decisions = relationship("Decision", back_populates="client")
    actions = relationship("Action", back_populates="client")


class Meeting(Base):
    """Meeting model."""
    __tablename__ = "meetings"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=True)
    calendar_event_id = Column(String, nullable=True)  # Google Calendar event ID
    zoom_meeting_id = Column(String, nullable=True)  # Zoom meeting ID
    title = Column(String, nullable=False)
    scheduled_time = Column(DateTime, nullable=False)
    duration_minutes = Column(Integer, nullable=True)
    attendees = Column(JSON, default=list)  # List of attendee emails/names
    status = Column(String, default="scheduled")  # scheduled, completed, cancelled
    transcript = Column(Text, nullable=True)  # Zoom transcript
    recording_url = Column(String, nullable=True)  # Zoom recording URL
    summary = Column(Text, nullable=True)  # Post-meeting summary
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="meetings")
    client = relationship("Client", back_populates="meetings")
    decisions = relationship("Decision", back_populates="meeting")
    actions = relationship("Action", back_populates="meeting")


class Decision(Base):
    """Decision made during a meeting."""
    __tablename__ = "decisions"
    
    id = Column(Integer, primary_key=True, index=True)
    meeting_id = Column(Integer, ForeignKey("meetings.id"), nullable=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
    description = Column(Text, nullable=False)
    context = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    meeting = relationship("Meeting", back_populates="decisions")
    client = relationship("Client", back_populates="decisions")


class Action(Base):
    """Action item from a meeting."""
    __tablename__ = "actions"
    
    id = Column(Integer, primary_key=True, index=True)
    meeting_id = Column(Integer, ForeignKey("meetings.id"), nullable=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
    description = Column(Text, nullable=False)
    assignee = Column(String, nullable=True)  # Email or name
    due_date = Column(DateTime, nullable=True)
    status = Column(String, default="pending")  # pending, in_progress, completed
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    meeting = relationship("Meeting", back_populates="actions")
    client = relationship("Client", back_populates="actions")


class MemoryEntry(Base):
    """Persistent memory entries for user/client context."""
    __tablename__ = "memory_entries"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=True)
    key = Column(String, nullable=False)  # e.g., "communication_style", "preferences"
    value = Column(Text, nullable=False)  # JSON or text
    extra_data = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Note: SQLite autoincrement is handled automatically

