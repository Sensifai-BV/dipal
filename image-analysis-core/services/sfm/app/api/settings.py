from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict

fastapi_tags_metadata: list[dict[str, str]] = []


class APISettings(BaseSettings):
    """API metadata configuration."""

    version: str = "0.0.0"
    prefix: str = ""
    description: str = ""
    title: str = "Structure from Motion"
    summary: str = ""

    model_config = SettingsConfigDict(
        env_prefix="API_",
        env_file=".env",
        extra="ignore",
        case_sensitive=False,
    )


class ServerSettings(BaseSettings):
    """Server listen configuration."""

    host: str = "127.0.0.1"
    port: int = 8080
    workers: int = 0

    model_config = SettingsConfigDict(
        env_prefix="SERVER_",
        env_file=".env",
        extra="ignore",
        case_sensitive=False,
    )
