"""Google Drive client."""

from typing import List, Dict, Any, Optional
from googleapiclient.discovery import build
from app.integrations.google_auth import get_google_credentials


class GoogleDriveClient:
    """Client for interacting with Google Drive API."""
    
    def __init__(self):
        creds = get_google_credentials()
        self.service = build('drive', 'v3', credentials=creds)
    
    def search_files(
        self, 
        query: str, 
        max_results: int = 10,
        mime_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for files in Google Drive.
        
        Args:
            query: Search query (e.g., "name contains 'proposal'")
            max_results: Maximum number of results
            mime_type: Optional MIME type filter (e.g., "application/pdf")
        
        Returns:
            List of file dictionaries
        """
        try:
            query_string = query
            if mime_type:
                query_string = f"{query} and mimeType='{mime_type}'"
            
            results = self.service.files().list(
                q=query_string,
                pageSize=max_results,
                fields="files(id, name, mimeType, webViewLink, modifiedTime, owners)"
            ).execute()
            
            files = results.get('files', [])
            return files
        except Exception as e:
            raise Exception(f"Error searching Drive files: {str(e)}")
    
    def get_file_by_id(self, file_id: str) -> Optional[Dict[str, Any]]:
        """
        Get file metadata by ID.
        
        Args:
            file_id: Google Drive file ID
        
        Returns:
            File dictionary or None if not found
        """
        try:
            file = self.service.files().get(
                fileId=file_id,
                fields="id, name, mimeType, webViewLink, modifiedTime, owners, description"
            ).execute()
            return file
        except Exception as e:
            raise Exception(f"Error fetching file: {str(e)}")
    
    def get_file_content(self, file_id: str) -> Optional[str]:
        """
        Get text content of a file (for Google Docs, Sheets, etc.).
        
        Args:
            file_id: Google Drive file ID
        
        Returns:
            File content as string or None
        """
        try:
            file = self.service.files().get(fileId=file_id).execute()
            mime_type = file.get('mimeType', '')
            
            # For Google Docs, export as plain text
            if 'document' in mime_type:
                content = self.service.files().export(
                    fileId=file_id,
                    mimeType='text/plain'
                ).execute()
                return content.decode('utf-8')
            
            # For other text files, download directly
            elif 'text' in mime_type:
                content = self.service.files().get_media(fileId=file_id).execute()
                return content.decode('utf-8')
            
            return None
        except Exception as e:
            raise Exception(f"Error fetching file content: {str(e)}")
    
    def search_files_by_client_name(self, client_name: str, max_results: int = 10) -> List[Dict[str, Any]]:
        """
        Search for files related to a client by name.
        
        Args:
            client_name: Client name or company name
            max_results: Maximum number of results
        
        Returns:
            List of file dictionaries
        """
        query = f"name contains '{client_name}' or fullText contains '{client_name}'"
        return self.search_files(query, max_results=max_results)
    
    def get_recent_files(self, max_results: int = 10) -> List[Dict[str, Any]]:
        """
        Get recently modified files.
        
        Args:
            max_results: Maximum number of results
        
        Returns:
            List of file dictionaries
        """
        try:
            results = self.service.files().list(
                orderBy='modifiedTime desc',
                pageSize=max_results,
                fields="files(id, name, mimeType, webViewLink, modifiedTime, owners)"
            ).execute()
            
            files = results.get('files', [])
            return files
        except Exception as e:
            raise Exception(f"Error fetching recent files: {str(e)}")

