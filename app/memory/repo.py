"""Memory repository for read/write operations."""

from typing import Optional, List, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from app.memory.models import (
    User, Client, Meeting, Decision, Action, MemoryEntry
)
from app.memory.schemas import (
    UserCreate, ClientCreate, MeetingCreate, MeetingUpdate,
    DecisionCreate, ActionCreate, MemoryEntryCreate
)


class MemoryRepository:
    """Repository for memory operations."""
    
    def __init__(self, db: Session):
        self.db = db
    
    # User operations
    def get_user_by_email(self, email: str) -> Optional[User]:
        """Get user by email."""
        return self.db.query(User).filter(User.email == email).first()
    
    def create_user(self, user_data: UserCreate) -> User:
        """Create a new user."""
        user = User(**user_data.dict())
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user
    
    def get_or_create_user(self, email: str, name: Optional[str] = None) -> User:
        """Get existing user or create new one."""
        user = self.get_user_by_email(email)
        if not user:
            user = self.create_user(UserCreate(email=email, name=name))
        return user
    
    # Client operations
    def get_client_by_hubspot_id(self, hubspot_id: str) -> Optional[Client]:
        """Get client by HubSpot ID."""
        return self.db.query(Client).filter(Client.hubspot_id == hubspot_id).first()
    
    def create_client(self, client_data: ClientCreate) -> Client:
        """Create a new client."""
        client = Client(**client_data.dict())
        self.db.add(client)
        self.db.commit()
        self.db.refresh(client)
        return client
    
    def get_clients_by_user(self, user_id: int) -> List[Client]:
        """Get all clients for a user."""
        return self.db.query(Client).filter(Client.user_id == user_id).all()
    
    def get_client_by_id(self, client_id: int) -> Optional[Client]:
        """Get client by ID."""
        return self.db.query(Client).filter(Client.id == client_id).first()
    
    # Meeting operations
    def create_meeting(self, meeting_data: MeetingCreate) -> Meeting:
        """Create a new meeting."""
        meeting = Meeting(**meeting_data.dict())
        self.db.add(meeting)
        self.db.commit()
        self.db.refresh(meeting)
        return meeting
    
    def get_meeting_by_id(self, meeting_id: int) -> Optional[Meeting]:
        """Get meeting by ID."""
        return self.db.query(Meeting).filter(Meeting.id == meeting_id).first()
    
    def get_meetings_by_user(self, user_id: int, limit: int = 10) -> List[Meeting]:
        """Get recent meetings for a user."""
        return (
            self.db.query(Meeting)
            .filter(Meeting.user_id == user_id)
            .order_by(Meeting.scheduled_time.desc())
            .limit(limit)
            .all()
        )
    
    def get_meetings_by_client(self, client_id: int, limit: int = 10) -> List[Meeting]:
        """Get recent meetings for a client."""
        return (
            self.db.query(Meeting)
            .filter(Meeting.client_id == client_id)
            .order_by(Meeting.scheduled_time.desc())
            .limit(limit)
            .all()
        )
    
    def update_meeting(self, meeting_id: int, update_data: MeetingUpdate) -> Optional[Meeting]:
        """Update a meeting."""
        meeting = self.get_meeting_by_id(meeting_id)
        if not meeting:
            return None
        
        for key, value in update_data.dict(exclude_unset=True).items():
            setattr(meeting, key, value)
        
        meeting.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(meeting)
        return meeting
    
    # Decision operations
    def create_decision(self, decision_data: DecisionCreate) -> Decision:
        """Create a new decision."""
        decision = Decision(**decision_data.dict())
        self.db.add(decision)
        self.db.commit()
        self.db.refresh(decision)
        return decision
    
    def get_decisions_by_client(self, client_id: int, limit: int = 20) -> List[Decision]:
        """Get recent decisions for a client."""
        return (
            self.db.query(Decision)
            .filter(Decision.client_id == client_id)
            .order_by(Decision.created_at.desc())
            .limit(limit)
            .all()
        )
    
    # Action operations
    def create_action(self, action_data: ActionCreate) -> Action:
        """Create a new action."""
        action = Action(**action_data.dict())
        self.db.add(action)
        self.db.commit()
        self.db.refresh(action)
        return action
    
    def get_actions_by_client(self, client_id: int, status: Optional[str] = None) -> List[Action]:
        """Get actions for a client, optionally filtered by status."""
        query = self.db.query(Action).filter(Action.client_id == client_id)
        if status:
            query = query.filter(Action.status == status)
        return query.order_by(Action.due_date.asc(), Action.created_at.desc()).all()
    
    def get_pending_actions_by_client(self, client_id: int) -> List[Action]:
        """Get pending actions for a client."""
        return self.get_actions_by_client(client_id, status="pending")
    
    # Memory entry operations
    def get_memory_entries(
        self, 
        user_id: int, 
        client_id: Optional[int] = None,
        key: Optional[str] = None
    ) -> List[MemoryEntry]:
        """Get memory entries for a user/client."""
        query = self.db.query(MemoryEntry).filter(MemoryEntry.user_id == user_id)
        
        if client_id:
            query = query.filter(MemoryEntry.client_id == client_id)
        elif client_id is None:
            # If client_id is explicitly None, get only user-level memories
            query = query.filter(MemoryEntry.client_id.is_(None))
        
        if key:
            query = query.filter(MemoryEntry.key == key)
        
        return query.order_by(MemoryEntry.updated_at.desc()).all()
    
    def get_memory_entry(
        self, 
        user_id: int, 
        key: str,
        client_id: Optional[int] = None
    ) -> Optional[MemoryEntry]:
        """Get a specific memory entry."""
        query = self.db.query(MemoryEntry).filter(
            and_(
                MemoryEntry.user_id == user_id,
                MemoryEntry.key == key
            )
        )
        
        if client_id:
            query = query.filter(MemoryEntry.client_id == client_id)
        else:
            query = query.filter(MemoryEntry.client_id.is_(None))
        
        return query.first()
    
    def create_or_update_memory_entry(
        self, 
        memory_data: MemoryEntryCreate
    ) -> MemoryEntry:
        """Create or update a memory entry."""
        existing = self.get_memory_entry(
            memory_data.user_id,
            memory_data.key,
            memory_data.client_id
        )
        
        if existing:
            existing.value = memory_data.value
            if memory_data.extra_data:
                existing.extra_data = memory_data.extra_data
            existing.updated_at = datetime.utcnow()
            self.db.commit()
            self.db.refresh(existing)
            return existing
        else:
            entry = MemoryEntry(**memory_data.dict())
            self.db.add(entry)
            self.db.commit()
            self.db.refresh(entry)
            return entry
    
    def get_client_context(self, client_id: int) -> Dict[str, Any]:
        """Get comprehensive context for a client."""
        client = self.get_client_by_id(client_id)
        if not client:
            return {}
        
        meetings = self.get_meetings_by_client(client_id, limit=5)
        decisions = self.get_decisions_by_client(client_id, limit=10)
        actions = self.get_actions_by_client(client_id)
        memories = self.get_memory_entries(client.user_id, client_id=client_id)
        
        return {
            "client": {
                "id": client.id,
                "name": client.name,
                "email": client.email,
                "company": client.company,
                "extra_data": client.extra_data,
            },
            "recent_meetings": [
                {
                    "id": m.id,
                    "title": m.title,
                    "scheduled_time": m.scheduled_time.isoformat(),
                    "status": m.status,
                    "summary": m.summary,
                }
                for m in meetings
            ],
            "decisions": [
                {
                    "id": d.id,
                    "description": d.description,
                    "context": d.context,
                    "created_at": d.created_at.isoformat(),
                }
                for d in decisions
            ],
            "actions": [
                {
                    "id": a.id,
                    "description": a.description,
                    "assignee": a.assignee,
                    "due_date": a.due_date.isoformat() if a.due_date else None,
                    "status": a.status,
                }
                for a in actions
            ],
            "memories": [
                {
                    "key": m.key,
                    "value": m.value,
                    "extra_data": m.extra_data,
                }
                for m in memories
            ],
        }

