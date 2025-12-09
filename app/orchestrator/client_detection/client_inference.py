"""Client inference service - infers client ID from meeting title and attendees."""

import re
from typing import Optional, List, Dict, Any
from app.memory.repo import MemoryRepository
from app.llm.gemini_client import GeminiClient


class ClientInferenceService:
    """Service for inferring client ID from meeting information."""
    
    def __init__(self, memory_repository: MemoryRepository, llm_client: GeminiClient):
        """
        Initialize the client inference service.
        
        Args:
            memory_repository: Repository for accessing client data
            llm_client: LLM client for intelligent inference
        """
        self.memory = memory_repository
        self.llm = llm_client
    
    def match_name_to_client_id(
        self,
        name: str,
        user_id: Optional[int] = None
    ) -> Optional[int]:
        """
        Match a name to a client ID using exact and fuzzy matching.
        
        Args:
            name: Name to match (can be client name, company name, or partial match)
            user_id: Optional user ID to filter clients
        
        Returns:
            Client ID if match found, None otherwise
        """
        if not name or not name.strip():
            return None
        
        name = name.strip()
        
        # Step 1: Try exact match (case-insensitive)
        clients = self.memory.search_clients_by_name(name, user_id=user_id)
        if clients:
            # Check for exact match (case-insensitive)
            for client in clients:
                if client.name.lower() == name.lower():
                    return client.id
        
        # Step 2: Try fuzzy matching if exact match fails
        if clients:
            # If search_clients_by_name found results, use the first one
            # (it already does ILIKE matching, so it's somewhat fuzzy)
            return clients[0].id
        
        # Step 3: Try matching against company name
        # Note: This requires querying all clients, which we'll do via search
        # Since search_clients_by_name uses ILIKE, it should catch company names too
        # if they're in the name field
        
        # Step 4: Try partial word matching
        # Split name into words and try matching each significant word
        words = [w.strip() for w in name.split() if len(w.strip()) > 2]  # Ignore short words
        for word in words:
            if len(word) >= 3:  # Only try words with 3+ characters
                word_clients = self.memory.search_clients_by_name(word, user_id=user_id)
                if word_clients:
                    # Prefer exact word match
                    for client in word_clients:
                        if word.lower() in client.name.lower():
                            return client.id
        
        return None
    
    def infer_client_name_from_text(
        self,
        meeting_title: str,
        attendees: Optional[List[str]] = None
    ) -> Optional[str]:
        """
        Use LLM to infer client name from meeting title and attendees.
        
        Args:
            meeting_title: Meeting title/name
            attendees: Optional list of attendee names/emails
        
        Returns:
            Inferred client name or None
        """
        if not meeting_title:
            return None
        
        # Build context for LLM
        context_parts = [f"Meeting Title: {meeting_title}"]
        
        if attendees:
            attendees_str = ", ".join(attendees) if isinstance(attendees, list) else str(attendees)
            context_parts.append(f"Attendees: {attendees_str}")
        
        prompt = f"""Analyze the following meeting information and extract the client or company name.

{chr(10).join(context_parts)}

Extract the client/company name from this meeting information. 
- Look for company names, client names, or organization names
- Ignore common words like "meeting", "call", "discussion"
- Return only the client/company name, nothing else
- If you cannot identify a clear client name, return "null"

Respond with just the client name or "null" if unclear."""

        try:
            response = self.llm.llm_chat(
                prompt=prompt,
                response_format="text",
                temperature=0.3,  # Lower temperature for more consistent extraction
            )
            
            if response and isinstance(response, str):
                response = response.strip()
                # Check if LLM returned "null" or similar
                if response.lower() in ["null", "none", "n/a", "unknown", ""]:
                    return None
                return response
        except Exception as e:
            print(f"Error in LLM client inference: {e}")
            return None
        
        return None
    
    def infer_client_id(
        self,
        meeting_title: str,
        attendees: Optional[List[str]] = None,
        user_id: Optional[int] = None
    ) -> Optional[int]:
        """
        Infer client ID from meeting title and attendees using multiple strategies.
        
        Strategy:
        1. Extract potential client names from title (exact matching)
        2. Try fuzzy matching against known clients
        3. Use LLM to infer client name, then match to client ID
        
        Args:
            meeting_title: Meeting title/name
            attendees: Optional list of attendee names/emails
            user_id: Optional user ID to filter clients
        
        Returns:
            Client ID if found, None otherwise
        """
        if not meeting_title:
            return None
        
        # Strategy 1: Try direct matching of meeting title against client names
        # Extract potential client names from title (common patterns)
        potential_names = self._extract_potential_client_names(meeting_title)
        
        for name in potential_names:
            client_id = self.match_name_to_client_id(name, user_id=user_id)
            if client_id:
                return client_id
        
        # Strategy 2: Try matching the entire title
        client_id = self.match_name_to_client_id(meeting_title, user_id=user_id)
        if client_id:
            return client_id
        
        # Strategy 3: Use LLM to infer client name, then match
        inferred_name = self.infer_client_name_from_text(meeting_title, attendees)
        if inferred_name:
            client_id = self.match_name_to_client_id(inferred_name, user_id=user_id)
            if client_id:
                return client_id
        
        return None
    
    def _extract_potential_client_names(self, meeting_title: str) -> List[str]:
        """
        Extract potential client names from meeting title using common patterns.
        
        Args:
            meeting_title: Meeting title
        
        Returns:
            List of potential client names to try matching
        """
        if not meeting_title:
            return []
        
        potential_names = []
        
        # Pattern 1: "X Meeting" or "Meeting with X"
        patterns = [
            r'^([A-Z][A-Za-z0-9\s&]+?)\s+Meeting',
            r'Meeting\s+with\s+([A-Z][A-Za-z0-9\s&]+?)(?:\s|$|:)',
            r'([A-Z][A-Za-z0-9\s&]+?)\s+X\s+',
            r'\s+X\s+([A-Z][A-Za-z0-9\s&]+?)(?:\s|$|:)',
            r'([A-Z]{2,})\s+',  # Acronyms like "MTCA", "IBM"
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, meeting_title, re.IGNORECASE)
            for match in matches:
                if isinstance(match, tuple):
                    match = match[0] if match else ""
                if match and len(match.strip()) >= 2:
                    potential_names.append(match.strip())
        
        # Also try the full title if it's short (likely to be a client name)
        if len(meeting_title.split()) <= 5:
            potential_names.append(meeting_title)
        
        # Remove duplicates while preserving order
        seen = set()
        unique_names = []
        for name in potential_names:
            name_lower = name.lower()
            if name_lower not in seen:
                seen.add(name_lower)
                unique_names.append(name)
        
        return unique_names

