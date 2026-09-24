"""Orthomosaic Service Settings"""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class CallbackSettings(BaseSettings):
    """API Gateway callback configuration."""
    
    url: str = "http://api_gateway:8080"
    callback_endpoint: str = "/jobs/subservice-callback"
    timeout_seconds: float = 30.0
    
    model_config = SettingsConfigDict(
        env_prefix="API_GATEWAY_",
        env_file=".env",
        extra="ignore",
        case_sensitive=False,
    )
    
    @property
    def callback_url(self) -> str:
        """Full callback URL."""
        return f"{self.url.rstrip('/')}{self.callback_endpoint}"
