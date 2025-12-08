"""Google OAuth authentication helper."""

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from app.config import settings
import os


def get_google_credentials():
    """Get Google OAuth credentials."""
    creds = None
    
    # Check if token file exists
    if os.path.exists(settings.google_token_file):
        creds = Credentials.from_authorized_user_file(settings.google_token_file, settings.google_scopes_list)
    
    # If no valid credentials, try to get from environment or file
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            # Try to use client_secret.json file
            if os.path.exists(settings.google_client_secret_file):
                flow = InstalledAppFlow.from_client_secrets_file(
                    settings.google_client_secret_file,
                    settings.google_scopes_list
                )
                creds = flow.run_local_server(port=0)
            
            # Save credentials for next run
            if creds:
                with open(settings.google_token_file, 'w') as token:
                    token.write(creds.to_json())
    
    if not creds:
        raise Exception("Google credentials not available. Please authenticate.")
    
    return creds

