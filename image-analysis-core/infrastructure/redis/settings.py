from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class RedisSettings(BaseSettings):
    """Redis connection settings."""

    host: str = "localhost"
    port: int = 6379
    db: int = 0
    password: str | None = None
    decode_responses: bool = True
    socket_timeout: int = 5
    socket_connect_timeout: int = 5
    url: str | None = None

    model_config = SettingsConfigDict(
        env_prefix="REDIS_",
        env_file=".env",
        extra="ignore",
        case_sensitive=False,
    )

    @property
    def connection_url(self) -> str:
        """Generate Redis URL from settings or return explicit URL."""
        if self.url:
            return self.url
        auth = f":{self.password}@" if self.password else ""
        return f"redis://{auth}{self.host}:{self.port}/{self.db}"
