from __future__ import annotations

import json
from datetime import timedelta
from typing import Any

import redis

from infrastructure.logging import get_logger

from .settings import RedisSettings

__all__ = ["RedisClient"]

logger = get_logger(__name__)


class RedisClient:
    """Redis client wrapper with connection pooling."""

    def __init__(self, settings: RedisSettings):
        self.settings = settings
        self._pool: redis.ConnectionPool | None = None
        self._client: redis.Redis | None = None

    def _get_pool(self) -> redis.ConnectionPool:
        """Get or create connection pool."""
        if self._pool is None:
            self._pool = redis.ConnectionPool(
                host=self.settings.host,
                port=self.settings.port,
                db=self.settings.db,
                password=self.settings.password,
                decode_responses=self.settings.decode_responses,
                socket_timeout=self.settings.socket_timeout,
                socket_connect_timeout=self.settings.socket_connect_timeout,
            )
        return self._pool

    @property
    def client(self) -> redis.Redis:
        """Get Redis client instance."""
        if self._client is None:
            self._client = redis.Redis(connection_pool=self._get_pool())
        return self._client

    def ping(self) -> bool:
        """Check Redis connection."""
        try:
            return self.client.ping()
        except redis.RedisError as e:
            logger.error(f"Redis ping failed: {e}")
            return False

    def set(
        self,
        key: str,
        value: Any,
        ttl: int | timedelta | None = None,
    ) -> bool:
        """Set a key-value pair with optional TTL."""
        try:
            serialized = json.dumps(value, default=str)
            if ttl:
                return bool(self.client.setex(key, ttl, serialized))
            return bool(self.client.set(key, serialized))
        except (redis.RedisError, TypeError, ValueError) as e:
            logger.error(f"Redis set failed for key {key}: {e}")
            return False

    def get(self, key: str) -> Any | None:
        """Get value by key."""
        try:
            value = self.client.get(key)
            if value:
                return json.loads(value)
            return None
        except (redis.RedisError, json.JSONDecodeError) as e:
            logger.error(f"Redis get failed for key {key}: {e}")
            return None

    def delete(self, *keys: str) -> int:
        """Delete one or more keys."""
        try:
            return self.client.delete(*keys)
        except redis.RedisError as e:
            logger.error(f"Redis delete failed for keys {keys}: {e}")
            return 0

    def exists(self, key: str) -> bool:
        """Check if key exists."""
        try:
            return bool(self.client.exists(key))
        except redis.RedisError as e:
            logger.error(f"Redis exists check failed for key {key}: {e}")
            return False

    def hset(self, name: str, mapping: dict[str, Any]) -> int:
        """Set multiple hash fields."""
        try:
            serialized = {k: json.dumps(v, default=str) for k, v in mapping.items()}
            return self.client.hset(name, mapping=serialized)
        except redis.RedisError as e:
            logger.error(f"Redis hset failed for {name}: {e}")
            return 0

    def hget(self, name: str, key: str) -> Any | None:
        """Get a hash field value."""
        try:
            value = self.client.hget(name, key)
            if value:
                return json.loads(value)
            return None
        except (redis.RedisError, json.JSONDecodeError) as e:
            logger.error(f"Redis hget failed for {name}.{key}: {e}")
            return None

    def hgetall(self, name: str) -> dict[str, Any]:
        """Get all hash fields."""
        try:
            data = self.client.hgetall(name)
            return {k: json.loads(v) for k, v in data.items()}
        except (redis.RedisError, json.JSONDecodeError) as e:
            logger.error(f"Redis hgetall failed for {name}: {e}")
            return {}

    def expire(self, key: str, ttl: int | timedelta) -> bool:
        """Set key expiration."""
        try:
            return bool(self.client.expire(key, ttl))
        except redis.RedisError as e:
            logger.error(f"Redis expire failed for key {key}: {e}")
            return False

    def close(self):
        """Close connection pool."""
        if self._pool:
            self._pool.disconnect()
            self._pool = None
            self._client = None
