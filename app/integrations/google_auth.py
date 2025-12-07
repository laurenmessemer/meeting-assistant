"""Google OAuth helper using InstalledAppFlow."""

import os
from typing import List
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from app.config import settings


def get_google_credentials(scopes: List[str] = None) -> Credentials:
    """
    Get Google OAuth credentials using InstalledAppFlow.
    
    This function handles the OAuth flow for desktop applications.
    It will open a browser window for authentication on first use.
    
    Args:
        scopes: List of OAuth scopes. Defaults to settings.google_scopes_list
    
    Returns:
        Credentials object for making API calls
    """
    if scopes is None:
        scopes = settings.google_scopes_list
    
    token_file = settings.google_token_file
    client_secret_file = settings.google_client_secret_file
    
    creds = None
    
    # Load existing token if available
    if os.path.exists(token_file):
        creds = Credentials.from_authorized_user_file(token_file, scopes)
    
    # If there are no (valid) credentials available, let the user log in
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            # Try to use client_secret.json file first (if it exists)
            if os.path.exists(client_secret_file):
                flow = InstalledAppFlow.from_client_secrets_file(
                    client_secret_file, scopes
                )
            else:
                # Use client_id and client_secret from env vars
                client_config = {
                    "installed": {
                        "client_id": settings.google_client_id,
                        "client_secret": settings.google_client_secret,
                        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                        "token_uri": "https://oauth2.googleapis.com/token",
                        "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                        "redirect_uris": ["http://localhost"]
                    }
                }
                flow = InstalledAppFlow.from_client_config(
                    client_config, scopes
                )
            
            creds = flow.run_local_server(port=0)
        
        # Save the credentials for the next run
        with open(token_file, 'w') as token:
            token.write(creds.to_json())
    
    return creds

