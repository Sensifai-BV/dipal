"""Unit tests for Redis client and settings."""
import json
import unittest
from unittest.mock import MagicMock, patch

import sys
from pathlib import Path
root_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(root_path))


class TestRedisSettings(unittest.TestCase):
    """Test Redis settings configuration."""

    def test_redis_settings_defaults(self):
        """Test settings load correctly with env overrides."""
        with patch.dict('os.environ', {
            "REDIS_HOST": "test-redis",
            "REDIS_PORT": "6380",
            "REDIS_DB": "2",
        }, clear=False):
            from infrastructure.redis.settings import RedisSettings
            settings = RedisSettings()

            self.assertEqual(settings.host, "test-redis")
            self.assertEqual(settings.port, 6380)
            self.assertEqual(settings.db, 2)

    def test_redis_settings_from_env(self):
        """Test settings can be loaded from environment."""
        env_vars = {
            "REDIS_HOST": "redis-server",
            "REDIS_PORT": "6380",
            "REDIS_DB": "1",
            "REDIS_PASSWORD": "secret",
        }
        with patch.dict('os.environ', env_vars, clear=True):
            from infrastructure.redis.settings import RedisSettings
            settings = RedisSettings()

            self.assertEqual(settings.host, "redis-server")
            self.assertEqual(settings.port, 6380)
            self.assertEqual(settings.db, 1)
            self.assertEqual(settings.password, "secret")

    def test_redis_url_property_without_password(self):
        """Test Redis URL generation without password."""
        with patch.dict('os.environ', {"REDIS_HOST": "localhost", "REDIS_PORT": "6379", "REDIS_DB": "0"}, clear=True):
            from infrastructure.redis.settings import RedisSettings
            settings = RedisSettings()

            self.assertEqual(settings.connection_url, "redis://localhost:6379/0")

    def test_redis_url_property_with_password(self):
        """Test Redis URL generation with password."""
        env_vars = {
            "REDIS_HOST": "redis-server",
            "REDIS_PORT": "6379",
            "REDIS_DB": "2",
            "REDIS_PASSWORD": "mypassword",
        }
        with patch.dict('os.environ', env_vars, clear=True):
            from infrastructure.redis.settings import RedisSettings
            settings = RedisSettings()

            self.assertEqual(settings.connection_url, "redis://:mypassword@redis-server:6379/2")


class TestRedisClient(unittest.TestCase):
    """Test Redis client wrapper."""

    def test_redis_client_initialization(self):
        """Test client initializes with settings."""
        with patch.dict('os.environ', {"REDIS_HOST": "localhost"}, clear=True):
            from infrastructure.redis.settings import RedisSettings
            from infrastructure.redis.client import RedisClient

            settings = RedisSettings()
            with patch('redis.ConnectionPool'):
                with patch('redis.Redis'):
                    client = RedisClient(settings)
                    self.assertIsNotNone(client)

    def test_redis_set_with_ttl(self):
        """Test setting value with TTL."""
        with patch.dict('os.environ', {"REDIS_HOST": "localhost"}, clear=True):
            from infrastructure.redis.settings import RedisSettings
            from infrastructure.redis.client import RedisClient

            settings = RedisSettings()
            mock_redis = MagicMock()
            with patch('redis.ConnectionPool'):
                with patch('redis.Redis', return_value=mock_redis):
                    client = RedisClient(settings)

                    test_data = {"key": "value"}
                    client.set("test_key", test_data, ttl=3600)

                    mock_redis.setex.assert_called_once()
                    args, kwargs = mock_redis.setex.call_args
                    self.assertEqual(args[0], "test_key")
                    self.assertEqual(args[1], 3600)
                    self.assertEqual(json.loads(args[2]), test_data)

    def test_redis_set_without_ttl(self):
        """Test setting value without TTL."""
        with patch.dict('os.environ', {"REDIS_HOST": "localhost"}, clear=True):
            from infrastructure.redis.settings import RedisSettings
            from infrastructure.redis.client import RedisClient

            settings = RedisSettings()
            mock_redis = MagicMock()
            with patch('redis.ConnectionPool'):
                with patch('redis.Redis', return_value=mock_redis):
                    client = RedisClient(settings)

                    test_data = {"key": "value"}
                    client.set("test_key", test_data)

                    mock_redis.set.assert_called_once()

    def test_redis_get_existing_key(self):
        """Test getting existing key."""
        with patch.dict('os.environ', {"REDIS_HOST": "localhost"}, clear=True):
            from infrastructure.redis.settings import RedisSettings
            from infrastructure.redis.client import RedisClient

            settings = RedisSettings()
            mock_redis = MagicMock()
            expected_data = {"key": "value"}
            mock_redis.get.return_value = json.dumps(expected_data)

            with patch('redis.ConnectionPool'):
                with patch('redis.Redis', return_value=mock_redis):
                    client = RedisClient(settings)
                    result = client.get("test_key")
                    self.assertEqual(result, expected_data)

    def test_redis_get_nonexistent_key(self):
        """Test getting non-existent key returns None."""
        with patch.dict('os.environ', {"REDIS_HOST": "localhost"}, clear=True):
            from infrastructure.redis.settings import RedisSettings
            from infrastructure.redis.client import RedisClient

            settings = RedisSettings()
            mock_redis = MagicMock()
            mock_redis.get.return_value = None

            with patch('redis.ConnectionPool'):
                with patch('redis.Redis', return_value=mock_redis):
                    client = RedisClient(settings)
                    result = client.get("nonexistent_key")
                    self.assertIsNone(result)

    def test_redis_delete(self):
        """Test deleting a key."""
        with patch.dict('os.environ', {"REDIS_HOST": "localhost"}, clear=True):
            from infrastructure.redis.settings import RedisSettings
            from infrastructure.redis.client import RedisClient

            settings = RedisSettings()
            mock_redis = MagicMock()
            mock_redis.delete.return_value = 1

            with patch('redis.ConnectionPool'):
                with patch('redis.Redis', return_value=mock_redis):
                    client = RedisClient(settings)
                    result = client.delete("test_key")

                    self.assertEqual(result, 1)
                    mock_redis.delete.assert_called_once_with("test_key")

    def test_redis_exists(self):
        """Test checking if key exists."""
        with patch.dict('os.environ', {"REDIS_HOST": "localhost"}, clear=True):
            from infrastructure.redis.settings import RedisSettings
            from infrastructure.redis.client import RedisClient

            settings = RedisSettings()
            mock_redis = MagicMock()
            mock_redis.exists.return_value = 1

            with patch('redis.ConnectionPool'):
                with patch('redis.Redis', return_value=mock_redis):
                    client = RedisClient(settings)
                    result = client.exists("test_key")

                    self.assertTrue(result)


if __name__ == "__main__":
    unittest.main()
