"""Gmail client."""

from typing import List, Dict, Any, Optional
from googleapiclient.discovery import build
from app.integrations.google_auth import get_google_credentials


class GmailClient:
    """Client for interacting with Gmail API."""
    
    def __init__(self):
        creds = get_google_credentials()
        self.service = build('gmail', 'v1', credentials=creds)
    
    def search_messages(
        self, 
        query: str, 
        max_results: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Search for email messages.
        
        Args:
            query: Gmail search query (e.g., "from:example@email.com")
            max_results: Maximum number of results
        
        Returns:
            List of message dictionaries
        """
        try:
            results = self.service.users().messages().list(
                userId='me',
                q=query,
                maxResults=max_results
            ).execute()
            
            messages = results.get('messages', [])
            return messages
        except Exception as e:
            raise Exception(f"Error searching Gmail messages: {str(e)}")
    
    def get_message(self, message_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a specific email message by ID.
        
        Args:
            message_id: Gmail message ID
        
        Returns:
            Message dictionary or None if not found
        """
        try:
            message = self.service.users().messages().get(
                userId='me',
                id=message_id,
                format='full'
            ).execute()
            return message
        except Exception as e:
            raise Exception(f"Error fetching message: {str(e)}")
    
    def get_messages_with_client(
        self, 
        client_email: str, 
        max_results: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get email messages with a specific client.
        
        Args:
            client_email: Client's email address
            max_results: Maximum number of results
        
        Returns:
            List of message dictionaries
        """
        query = f"from:{client_email} OR to:{client_email}"
        return self.search_messages(query, max_results=max_results)
    
    def extract_message_text(self, message: Dict[str, Any]) -> str:
        """
        Extract plain text from an email message.
        
        Args:
            message: Gmail message dictionary
        
        Returns:
            Plain text content
        """
        payload = message.get('payload', {})
        body = ""
        
        if 'parts' in payload:
            for part in payload['parts']:
                if part['mimeType'] == 'text/plain':
                    data = part['body'].get('data')
                    if data:
                        import base64
                        body = base64.urlsafe_b64decode(data).decode('utf-8')
                        break
        else:
            if payload.get('mimeType') == 'text/plain':
                data = payload['body'].get('data')
                if data:
                    import base64
                    body = base64.urlsafe_b64decode(data).decode('utf-8')
        
        return body
    
    def get_email_tone_samples(
        self, 
        client_email: str, 
        max_samples: int = 5
    ) -> List[str]:
        """
        Get sample email text to analyze communication tone.
        
        Args:
            client_email: Client's email address
            max_samples: Maximum number of email samples
        
        Returns:
            List of email text samples
        """
        messages = self.get_messages_with_client(client_email, max_results=max_samples)
        samples = []
        
        for msg in messages:
            full_message = self.get_message(msg['id'])
            if full_message:
                text = self.extract_message_text(full_message)
                if text:
                    samples.append(text)
        
        return samples
    
    def get_thread(self, thread_id: str) -> Optional[Dict[str, Any]]:
        """
        Get an email thread by ID.
        
        Args:
            thread_id: Gmail thread ID
        
        Returns:
            Thread dictionary or None if not found
        """
        try:
            thread = self.service.users().threads().get(
                userId='me',
                id=thread_id
            ).execute()
            return thread
        except Exception as e:
            raise Exception(f"Error fetching thread: {str(e)}")


# Simple function wrappers - no business logic, just API calls
def search_gmail_messages(query: str, max_results: int = 10) -> List[Dict[str, Any]]:
    """
    Search for Gmail messages.
    
    Args:
        query: Gmail search query
        max_results: Maximum number of results
    
    Returns:
        List of message dictionaries
    """
    client = GmailClient()
    return client.search_messages(query, max_results)


def get_gmail_message(message_id: str) -> Optional[Dict[str, Any]]:
    """
    Get a Gmail message by ID.
    
    Args:
        message_id: Gmail message ID
    
    Returns:
        Message dictionary or None
    """
    client = GmailClient()
    return client.get_message(message_id)


def get_gmail_messages_with_client(client_email: str, max_results: int = 10) -> List[Dict[str, Any]]:
    """
    Get email messages with a specific client.
    
    Args:
        client_email: Client's email address
        max_results: Maximum number of results
    
    Returns:
        List of message dictionaries
    """
    client = GmailClient()
    return client.get_messages_with_client(client_email, max_results)


def extract_gmail_message_text(message: Dict[str, Any]) -> str:
    """
    Extract plain text from a Gmail message.
    
    Args:
        message: Gmail message dictionary
    
    Returns:
        Plain text content
    """
    client = GmailClient()
    return client.extract_message_text(message)

