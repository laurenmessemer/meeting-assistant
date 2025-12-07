"""Central configuration management."""

import os
from typing import List
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Database
    database_url: str = Field(..., env="DATABASE_URL")
    
    # LLM Configuration
    llm_provider: str = Field(default="gemini", env="LLM_PROVIDER")
    llm_api_key: str = Field(..., env="LLM_API_KEY")
    
    # HubSpot
    hubspot_api_key: str = Field(..., env="HUBSPOT_API_KEY")
    
    # Zoom Server-to-Server OAuth
    zoom_account_id: str = Field(..., env="ZOOM_ACCOUNT_ID")
    zoom_client_id: str = Field(..., env="ZOOM_CLIENT_ID")
    zoom_client_secret: str = Field(..., env="ZOOM_CLIENT_SECRET")
    
    # Google OAuth
    google_client_id: str = Field(..., env="GOOGLE_CLIENT_ID")
    google_client_secret: str = Field(..., env="GOOGLE_CLIENT_SECRET")
    google_client_secret_file: str = Field(default="client_secret.json", env="GOOGLE_CLIENT_SECRET_FILE")
    google_token_file: str = Field(default="token.json", env="GOOGLE_TOKEN_FILE")
    google_scopes: str = Field(
        default="https://www.googleapis.com/auth/calendar.readonly,https://www.googleapis.com/auth/drive.readonly,https://www.googleapis.com/auth/gmail.readonly",
        env="GOOGLE_SCOPES"
    )
    
    # Application
    app_name: str = Field(default="Meeting Assistant", env="APP_NAME")
    app_env: str = Field(default="development", env="APP_ENV")
    app_debug: bool = Field(default=True, env="APP_DEBUG")
    port: int = Field(default=8000, env="PORT")
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    
    @property
    def google_scopes_list(self) -> List[str]:
        """Parse Google scopes string into a list."""
        return [scope.strip() for scope in self.google_scopes.split(",") if scope.strip()]
    
    @property
    def debug(self) -> bool:
        """Alias for app_debug for backward compatibility."""
        return self.app_debug
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


# Global settings instance
settings = Settings()

