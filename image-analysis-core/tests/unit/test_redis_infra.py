"""Unit tests for infrastructure/redis (RedisClient + RedisSettings)."""
import unittest
from unittest.mock import MagicMock, patch
from unittest.mock import patch as mock_patch
import os
import json
import sys
from pathlib import Path

root_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(root_path))

from infrastructure.redis.settings import RedisSettings
from infrastructure.redis.client import RedisClient


class TestRedisSettings(unittest.TestCase):
    """Tests for RedisSettings model."""

    @patch.dict("os.environ", {}, clear=True)
    def test_defaults(self):
        s = RedisSettings(_env_file=None)
        self.assertEqual(s.host, "localhost")
        self.assertEqual(s.port, 6379)
        self.assertEqual(s.db, 0)
        self.assertIsNone(s.password)
        self.assertTrue(s.decode_responses)
        self.assertEqual(s.socket_timeout, 5)

    def test_connection_url_no_password(self):
        s = RedisSettings(host="redis-host", port=6380, db=2, _env_file=None)
        self.assertEqual(s.connection_url, "redis://redis-host:6380/2")

    def test_connection_url_with_password(self):
        s = RedisSettings(host="redis-host", password="secret", port=6379, db=1, _env_file=None)
        self.assertEqual(s.connection_url, "redis://:secret@redis-host:6379/1")

    def test_connection_url_explicit(self):
        s = RedisSettings(url="redis://custom:6379/0", _env_file=None)
        self.assertEqual(s.connection_url, "redis://custom:6379/0")


class TestRedisClient(unittest.TestCase):
    """Tests for RedisClient."""

    def setUp(self):
        self.settings = RedisSettings(host="localhost", port=6379)
        self.rc = RedisClient(self.settings)
        self.mock_redis = MagicMock()
        self.rc._client = self.mock_redis

    def test_ping_success(self):
        self.mock_redis.ping.return_value = True
        self.assertTrue(self.rc.ping())

    def test_ping_failure(self):
        import redis as redis_lib
        self.mock_redis.ping.side_effect = redis_lib.RedisError("Connection refused")
        self.assertFalse(self.rc.ping())

    def test_set_success(self):
        self.mock_redis.set.return_value = True
        result = self.rc.set("key1", {"data": "value"})
        self.assertTrue(result)

    def test_set_with_ttl(self):
        self.mock_redis.setex.return_value = True
        result = self.rc.set("key1", "value", ttl=60)
        self.assertTrue(result)
        self.mock_redis.setex.assert_called_once()

    def test_set_failure(self):
        import redis as redis_lib
        self.mock_redis.set.side_effect = redis_lib.RedisError("Error")
        self.assertFalse(self.rc.set("key1", "value"))

    def test_get_success(self):
        self.mock_redis.get.return_value = json.dumps({"key": "value"})
        result = self.rc.get("key1")
        self.assertEqual(result, {"key": "value"})

    def test_get_none(self):
        self.mock_redis.get.return_value = None
        self.assertIsNone(self.rc.get("key1"))

    def test_get_failure(self):
        import redis as redis_lib
        self.mock_redis.get.side_effect = redis_lib.RedisError("Error")
        self.assertIsNone(self.rc.get("key1"))

    def test_delete_success(self):
        self.mock_redis.delete.return_value = 1
        self.assertEqual(self.rc.delete("key1"), 1)

    def test_delete_failure(self):
        import redis as redis_lib
        self.mock_redis.delete.side_effect = redis_lib.RedisError("Error")
        self.assertEqual(self.rc.delete("key1"), 0)

    def test_exists_true(self):
        self.mock_redis.exists.return_value = 1
        self.assertTrue(self.rc.exists("key1"))

    def test_exists_false(self):
        self.mock_redis.exists.return_value = 0
        self.assertFalse(self.rc.exists("key1"))

    def test_hset_success(self):
        self.mock_redis.hset.return_value = 1
        self.assertEqual(self.rc.hset("hash1", {"f1": "v1"}), 1)

    def test_hget_success(self):
        self.mock_redis.hget.return_value = json.dumps("value")
        self.assertEqual(self.rc.hget("hash1", "f1"), "value")

    def test_hget_none(self):
        self.mock_redis.hget.return_value = None
        self.assertIsNone(self.rc.hget("hash1", "missing"))

    def test_hgetall_success(self):
        self.mock_redis.hgetall.return_value = {
            "f1": json.dumps("v1"), "f2": json.dumps("v2")
        }
        self.assertEqual(self.rc.hgetall("h"), {"f1": "v1", "f2": "v2"})

    def test_hgetall_failure(self):
        import redis as redis_lib
        self.mock_redis.hgetall.side_effect = redis_lib.RedisError("Error")
        self.assertEqual(self.rc.hgetall("h"), {})

    def test_expire_success(self):
        self.mock_redis.expire.return_value = True
        self.assertTrue(self.rc.expire("key1", 300))

    def test_close(self):
        mock_pool = MagicMock()
        self.rc._pool = mock_pool
        self.rc.close()
        mock_pool.disconnect.assert_called_once()
        self.assertIsNone(self.rc._pool)
        self.assertIsNone(self.rc._client)

    def test_client_property_creates_connection(self):
        fresh = RedisClient(self.settings)
        fresh._pool = None
        fresh._client = None
        with patch("redis.ConnectionPool") as mock_pool_cls, \
             patch("redis.Redis") as mock_redis_cls:
            mock_pool_cls.return_value = MagicMock()
            mock_redis_cls.return_value = MagicMock()
            _ = fresh.client
            mock_pool_cls.assert_called_once()
            mock_redis_cls.assert_called_once()


if __name__ == "__main__":
    unittest.main()
