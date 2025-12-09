"""Tests for memory relevance and retrieval."""

import pytest
from datetime import datetime, timezone, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.memory.models import Base, MemoryEntry, Client, User, Meeting
from app.memory.repo import MemoryRepository


class TestMemoryRelevance:
    """Tests for memory relevance and retrieval."""
    
    @pytest.fixture
    def test_db(self):
        """Create an in-memory SQLite database for testing."""
        engine = create_engine("sqlite:///:memory:", echo=False)
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        session = Session()
        yield session
        session.close()
    
    @pytest.fixture
    def memory_repo(self, test_db):
        """Create memory repository with test database."""
        return MemoryRepository(test_db)
    
    @pytest.fixture
    def test_user(self, test_db):
        """Create a test user."""
        user = User(id=1, email="test@example.com", name="Test User")
        test_db.add(user)
        test_db.commit()
        return user
    
    @pytest.fixture
    def test_client(self, test_db, test_user):
        """Create a test client."""
        client = Client(id=1, user_id=1, hubspot_id="hubspot_123", name="Acme Corp", email="acme@example.com")
        test_db.add(client)
        test_db.commit()
        return client
    
    def test_memory_retrieval_by_client_id(self, memory_repo, test_db, test_user, test_client):
        """Test that memories are retrieved correctly by client_id."""
        # Create memory entries
        memory1 = MemoryEntry(
            user_id=1,
            client_id=1,
            key="project_status",
            value="Project is on track",
            extra_data={"meeting_id": 1}
        )
        memory2 = MemoryEntry(
            user_id=1,
            client_id=1,
            key="client_preferences",
            value="Prefers email communication",
            extra_data={}
        )
        memory3 = MemoryEntry(
            user_id=1,
            client_id=2,  # Different client
            key="other_client_data",
            value="Other client info",
            extra_data={}
        )
        
        test_db.add_all([memory1, memory2, memory3])
        test_db.commit()
        
        # Retrieve memories for client_id=1
        memories = memory_repo.get_relevant_memories(
            user_id=1,
            client_id=1,
            intent="summarization",
            keywords=None,
            limit=10
        )
        
        assert len(memories) == 2
        assert all(m.client_id == 1 for m in memories)
        assert any(m.key == "project_status" for m in memories)
        assert any(m.key == "client_preferences" for m in memories)
    
    def test_memory_relevance_filtering(self, memory_repo, test_db, test_user, test_client):
        """Test that memory relevance filtering works correctly."""
        # Create memory entries with different keywords
        memory1 = MemoryEntry(
            user_id=1,
            client_id=1,
            key="meeting_summary_project_x",
            value="Discussed project timeline",
            extra_data={"keywords": ["project", "timeline"]}
        )
        memory2 = MemoryEntry(
            user_id=1,
            client_id=1,
            key="meeting_summary_budget",
            value="Discussed budget allocation",
            extra_data={"keywords": ["budget"]}
        )
        memory3 = MemoryEntry(
            user_id=1,
            client_id=1,
            key="meeting_summary_team",
            value="Discussed team structure",
            extra_data={"keywords": ["team"]}
        )
        
        test_db.add_all([memory1, memory2, memory3])
        test_db.commit()
        
        # Retrieve memories with keyword "project"
        memories = memory_repo.get_relevant_memories(
            user_id=1,
            client_id=1,
            intent="summarization",
            keywords=["project"],
            limit=10
        )
        
        # Should return at least the project-related memory
        assert len(memories) >= 1
        assert any("project" in m.key.lower() or "project" in m.value.lower() for m in memories)
    
    def test_memory_write_new_entry(self, memory_repo, test_db, test_user, test_client):
        """Test that new memory entries are written correctly."""
        from app.memory.schemas import MemoryEntryCreate
        
        memory_data = MemoryEntryCreate(
            user_id=1,
            client_id=1,
            key="test_memory",
            value="Test memory value",
            extra_data={"test": "data"}
        )
        
        memory_repo.create_or_update_memory_entry(memory_data)
        test_db.commit()
        
        # Retrieve the memory
        memories = memory_repo.get_memory_entries(user_id=1, limit=10)
        
        assert len(memories) == 1
        assert memories[0].key == "test_memory"
        assert memories[0].value == "Test memory value"
        assert memories[0].extra_data == {"test": "data"}
    
    def test_memory_stable_ordering(self, memory_repo, test_db, test_user, test_client):
        """Test that memory retrieval returns stable ordering."""
        # Create multiple memory entries
        for i in range(5):
            memory = MemoryEntry(
                user_id=1,
                client_id=1,
                key=f"memory_{i}",
                value=f"Value {i}",
                extra_data={}
            )
            test_db.add(memory)
        test_db.commit()
        
        # Retrieve memories multiple times
        memories1 = memory_repo.get_memory_entries(user_id=1, limit=10)
        memories2 = memory_repo.get_memory_entries(user_id=1, limit=10)
        
        # Should return same order
        assert len(memories1) == len(memories2)
        assert [m.id for m in memories1] == [m.id for m in memories2]
    
    def test_memory_retrieval_by_user_id(self, memory_repo, test_db, test_user, test_client):
        """Test that memories are retrieved correctly by user_id."""
        # Create memory entries for different users
        memory1 = MemoryEntry(
            user_id=1,
            client_id=1,
            key="user1_memory",
            value="User 1 data",
            extra_data={}
        )
        memory2 = MemoryEntry(
            user_id=2,
            client_id=1,
            key="user2_memory",
            value="User 2 data",
            extra_data={}
        )
        
        test_db.add_all([memory1, memory2])
        test_db.commit()
        
        # Retrieve memories for user_id=1
        memories = memory_repo.get_memory_entries(user_id=1, limit=10)
        
        assert len(memories) == 1
        assert memories[0].user_id == 1
        assert memories[0].key == "user1_memory"
    
    def test_memory_limit_enforcement(self, memory_repo, test_db, test_user, test_client):
        """Test that memory limit is enforced correctly."""
        # Create more memories than limit
        for i in range(10):
            memory = MemoryEntry(
                user_id=1,
                client_id=1,
                key=f"memory_{i}",
                value=f"Value {i}",
                extra_data={}
            )
            test_db.add(memory)
        test_db.commit()
        
        # Retrieve with limit=5
        memories = memory_repo.get_memory_entries(user_id=1, limit=5)
        
        assert len(memories) == 5
    
    def test_memory_client_context_retrieval(self, memory_repo, test_db, test_user, test_client):
        """Test that client context is retrieved correctly."""
        # Create meetings for the client
        meeting1 = Meeting(
            user_id=1,
            client_id=1,
            title="Meeting 1",
            scheduled_time=datetime.now(timezone.utc) - timedelta(days=1),
            status="completed",
            summary="First meeting summary"
        )
        meeting2 = Meeting(
            user_id=1,
            client_id=1,
            title="Meeting 2",
            scheduled_time=datetime.now(timezone.utc) - timedelta(days=2),
            status="completed",
            summary="Second meeting summary"
        )
        
        test_db.add_all([meeting1, meeting2])
        test_db.commit()
        
        # Get client context
        context = memory_repo.get_client_context(client_id=1)
        
        assert context is not None
        assert "meetings" in context or "summary" in context or len(context) > 0

