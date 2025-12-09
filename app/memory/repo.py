"""Memory repository for database operations."""

from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc
from datetime import datetime, timezone
from app.memory.models import (
    Meeting, MemoryEntry, Decision, Action, Client, User
)
from app.memory.schemas import (
    MemoryEntryCreate,
    DecisionCreate,
    ActionCreate,
    MeetingCreate,
    MeetingUpdate
)


class MemoryRepository:
    """Repository for memory and database operations."""
    
    def __init__(self, db: Session):
        self.db = db
    
    # Meeting operations
    def get_meeting_by_id(self, meeting_id: int) -> Optional[Meeting]:
        """Get a meeting by ID."""
        return self.db.query(Meeting).filter(Meeting.id == meeting_id).first()
    
    def get_meeting_by_calendar_event_id(self, calendar_event_id: str) -> Optional[Meeting]:
        """Get a meeting by calendar event ID."""
        return self.db.query(Meeting).filter(
            Meeting.calendar_event_id == calendar_event_id
        ).first()
    
    def get_meetings_by_client(self, client_id: int, limit: Optional[int] = None) -> List[Meeting]:
        """Get meetings for a client."""
        query = self.db.query(Meeting).filter(Meeting.client_id == client_id)
        query = query.order_by(desc(Meeting.scheduled_time))
        if limit:
            query = query.limit(limit)
        return query.all()
    
    def get_meetings_by_user(self, user_id: int, limit: Optional[int] = None) -> List[Meeting]:
        """Get meetings for a user."""
        query = self.db.query(Meeting).filter(Meeting.user_id == user_id)
        query = query.order_by(desc(Meeting.scheduled_time))
        if limit:
            query = query.limit(limit)
        return query.all()
    
    def create_meeting(self, meeting_data: MeetingCreate) -> Meeting:
        """Create a new meeting."""
        meeting = Meeting(
            user_id=meeting_data.user_id,
            client_id=meeting_data.client_id,
            calendar_event_id=meeting_data.calendar_event_id,
            zoom_meeting_id=meeting_data.zoom_meeting_id,
            title=meeting_data.title,
            scheduled_time=meeting_data.scheduled_time,
            transcript=meeting_data.transcript,
            status=meeting_data.status,
            attendees=meeting_data.attendees
        )
        self.db.add(meeting)
        self.db.commit()
        self.db.refresh(meeting)
        return meeting
    
    def update_meeting(self, meeting_id: int, update_data: MeetingUpdate) -> Optional[Meeting]:
        """Update a meeting."""
        meeting = self.get_meeting_by_id(meeting_id)
        if not meeting:
            return None
        
        if update_data.summary is not None:
            meeting.summary = update_data.summary
        if update_data.transcript is not None:
            meeting.transcript = update_data.transcript
        if update_data.status is not None:
            meeting.status = update_data.status
        
        meeting.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(meeting)
        return meeting
    
    # Decision operations
    def get_decisions_by_meeting_id(self, meeting_id: int) -> List[Decision]:
        """Get decisions for a meeting."""
        return self.db.query(Decision).filter(Decision.meeting_id == meeting_id).all()
    
    def get_decisions_by_client_id(self, client_id: int) -> List[Decision]:
        """Get decisions for a client."""
        return self.db.query(Decision).filter(Decision.client_id == client_id).all()
    
    def create_decision(self, decision_data: DecisionCreate) -> Decision:
        """Create a decision."""
        decision = Decision(
            meeting_id=decision_data.meeting_id,
            client_id=decision_data.client_id,
            description=decision_data.description,
            context=decision_data.context
        )
        self.db.add(decision)
        self.db.commit()
        self.db.refresh(decision)
        return decision
    
    def save_decisions(self, decisions: List[DecisionCreate]) -> List[Decision]:
        """Save multiple decisions."""
        created_decisions = []
        for decision_data in decisions:
            decision = self.create_decision(decision_data)
            created_decisions.append(decision)
        return created_decisions
    
    # Action operations
    def get_actions_by_meeting_id(self, meeting_id: int) -> List[Action]:
        """Get actions for a meeting."""
        return self.db.query(Action).filter(Action.meeting_id == meeting_id).all()
    
    def get_actions_by_client_id(self, client_id: int) -> List[Action]:
        """Get actions for a client."""
        return self.db.query(Action).filter(Action.client_id == client_id).all()
    
    def create_action(self, action_data: ActionCreate) -> Action:
        """Create an action item."""
        action = Action(
            meeting_id=action_data.meeting_id,
            client_id=action_data.client_id,
            description=action_data.description,
            assignee=action_data.assignee,
            due_date=action_data.due_date,
            status="pending"
        )
        self.db.add(action)
        self.db.commit()
        self.db.refresh(action)
        return action
    
    def save_tasks(self, tasks: List[ActionCreate]) -> List[Action]:
        """Save multiple action items/tasks."""
        created_actions = []
        for action_data in tasks:
            action = self.create_action(action_data)
            created_actions.append(action)
        return created_actions
    
    # Memory entry operations
    def get_memory_entries(
        self, 
        user_id: Optional[int] = None, 
        client_id: Optional[int] = None, 
        limit: int = 50
    ) -> List[MemoryEntry]:
        """
        Get memory entries, optionally filtered by user_id and/or client_id.
        
        Args:
            user_id: Optional user ID to filter by
            client_id: Optional client ID to filter by
            limit: Maximum number of results (default: 50)
        
        Returns:
            List of memory entries ordered by newest first (created_at DESC)
        """
        query = self.db.query(MemoryEntry)
        
        if user_id is not None:
            query = query.filter(MemoryEntry.user_id == user_id)
        
        if client_id is not None:
            query = query.filter(MemoryEntry.client_id == client_id)
        
        return query.order_by(desc(MemoryEntry.created_at)).limit(limit).all()
    
    def get_relevant_memories(
        self,
        user_id: int,
        client_id: Optional[int] = None,
        intent: Optional[str] = None,
        keywords: Optional[List[str]] = None,
        limit: int = 10
    ) -> List[MemoryEntry]:
        """
        Get relevant memories based on context.
        
        For now, implements recency-based relevance (most recent entries first).
        If keywords are provided, filters by keywords in key/value.
        Intent parameter is accepted but not used for filtering (for future enhancement).
        
        Args:
            user_id: User ID
            client_id: Optional client ID to filter by
            intent: Optional intent (accepted but not used for filtering currently)
            keywords: Optional keywords to search in key/value
            limit: Maximum number of results
        
        Returns:
            List of relevant memory entries ordered by newest first
        """
        query = self.db.query(MemoryEntry).filter(MemoryEntry.user_id == user_id)
        
        if client_id is not None:
            query = query.filter(MemoryEntry.client_id == client_id)
        
        # Note: Intent filtering is not implemented yet - using recency-based relevance
        # If intent is provided, it's accepted but doesn't filter results
        # This allows the method to work with tests that pass intent but don't store it
        
        if keywords:
            # Search for keywords in key or value
            keyword_filters = []
            for keyword in keywords:
                keyword_lower = keyword.lower()
                keyword_filters.append(
                    or_(
                        MemoryEntry.key.ilike(f"%{keyword_lower}%"),
                        MemoryEntry.value.ilike(f"%{keyword_lower}%")
                    )
                )
            if keyword_filters:
                query = query.filter(or_(*keyword_filters))
        
        return query.order_by(desc(MemoryEntry.created_at)).limit(limit).all()
    
    def create_or_update_memory_entry(self, memory_data: MemoryEntryCreate) -> MemoryEntry:
        """Create or update a memory entry."""
        # Try to find existing entry with same key
        existing = self.db.query(MemoryEntry).filter(
            and_(
                MemoryEntry.user_id == memory_data.user_id,
                MemoryEntry.client_id == memory_data.client_id,
                MemoryEntry.key == memory_data.key
            )
        ).first()
        
        if existing:
            existing.value = memory_data.value
            if memory_data.extra_data:
                existing.extra_data = memory_data.extra_data
            existing.updated_at = datetime.utcnow()
            self.db.commit()
            self.db.refresh(existing)
            return existing
        else:
            memory_entry = MemoryEntry(
                user_id=memory_data.user_id,
                client_id=memory_data.client_id,
                key=memory_data.key,
                value=memory_data.value,
                extra_data=memory_data.extra_data or {}
            )
            self.db.add(memory_entry)
            self.db.commit()
            self.db.refresh(memory_entry)
            return memory_entry
    
    def get_memory_by_key(
        self,
        user_id: int,
        key: str,
        client_id: Optional[int] = None
    ) -> Optional[MemoryEntry]:
        """
        Get the most recent memory entry with the given key.
        
        Args:
            user_id: User ID (required)
            key: Memory key to look up
            client_id: Optional client ID to filter by
        
        Returns:
            Most recent MemoryEntry with the given key, or None if not found
        """
        query = self.db.query(MemoryEntry).filter(
            and_(
                MemoryEntry.user_id == user_id,
                MemoryEntry.key == key
            )
        )
        
        if client_id is not None:
            query = query.filter(MemoryEntry.client_id == client_id)
        
        return query.order_by(desc(MemoryEntry.updated_at)).first()
    
    def save_memory_by_key(
        self,
        user_id: int,
        key: str,
        value: str,
        client_id: Optional[int] = None,
        extra_data: Optional[Dict[str, Any]] = None
    ) -> MemoryEntry:
        """
        Save or update a memory entry by key using the upsert pattern.
        
        Args:
            user_id: User ID (required)
            key: Memory key
            value: Memory value
            client_id: Optional client ID
            extra_data: Optional additional metadata
        
        Returns:
            Created or updated MemoryEntry
        """
        memory_data = MemoryEntryCreate(
            user_id=user_id,
            client_id=client_id,
            key=key,
            value=value,
            extra_data=extra_data
        )
        
        return self.create_or_update_memory_entry(memory_data)
    
    def save_interaction_memory(
        self,
        user_id: int,
        client_id: Optional[int],
        message: str,
        response: str,
        intent: Optional[str] = None,
        tool_used: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> MemoryEntry:
        """
        Save interaction memory from a conversation.
        
        Args:
            user_id: User ID
            client_id: Optional client ID
            message: User message
            response: Assistant response
            intent: Optional intent
            tool_used: Optional tool that was used
            metadata: Optional additional metadata
        
        Returns:
            Created memory entry
        """
        extra_data = metadata or {}
        if intent:
            extra_data["intent"] = intent
        if tool_used:
            extra_data["tool_used"] = tool_used
        extra_data["timestamp"] = datetime.utcnow().isoformat()
        
        memory_data = MemoryEntryCreate(
            user_id=user_id,
            client_id=client_id,
            key="interaction",
            value=f"User: {message}\nAssistant: {response}",
            extra_data=extra_data
        )
        
        return self.create_or_update_memory_entry(memory_data)
    
    # Client operations
    def get_client_by_id(self, client_id: int) -> Optional[Client]:
        """Get a client by ID."""
        return self.db.query(Client).filter(Client.id == client_id).first()
    
    def search_clients_by_name(self, name: str, user_id: Optional[int] = None) -> List[Client]:
        """Search for clients by name."""
        query = self.db.query(Client)
        if user_id:
            query = query.filter(Client.user_id == user_id)
        query = query.filter(Client.name.ilike(f"%{name}%"))
        return query.all()
    
    def get_client_context(self, client_id: int) -> Dict[str, Any]:
        """
        Get comprehensive client context.
        
        Returns:
            Dictionary with client info, recent meetings, decisions, actions
        """
        client = self.get_client_by_id(client_id)
        if not client:
            return {}
        
        context = {
            "client_id": client.id,
            "name": client.name,
            "email": client.email,
            "company": client.company,
            "extra_data": client.extra_data or {}
        }
        
        # Get recent meetings
        recent_meetings = self.get_meetings_by_client(client_id, limit=5)
        context["recent_meetings"] = [
            {
                "id": m.id,
                "title": m.title,
                "scheduled_time": m.scheduled_time.isoformat() if m.scheduled_time else None,
                "status": m.status,
                "has_summary": m.summary is not None
            }
            for m in recent_meetings
        ]
        
        # Get recent decisions
        recent_decisions = self.get_decisions_by_client_id(client_id)
        context["recent_decisions"] = [
            {
                "id": d.id,
                "description": d.description,
                "context": d.context,
                "meeting_id": d.meeting_id
            }
            for d in recent_decisions[-10:]  # Last 10
        ]
        
        # Get recent actions
        recent_actions = self.get_actions_by_client_id(client_id)
        context["recent_actions"] = [
            {
                "id": a.id,
                "description": a.description,
                "assignee": a.assignee,
                "status": a.status,
                "due_date": a.due_date.isoformat() if a.due_date else None
            }
            for a in recent_actions[-10:]  # Last 10
        ]
        
        return context
