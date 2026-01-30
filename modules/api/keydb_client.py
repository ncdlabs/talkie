"""
KeyDB client wrapper (Redis-compatible).
KeyDB is 5x faster than Redis and uses the same protocol.
"""

from __future__ import annotations

import logging

import redis  # redis-py works with KeyDB (same protocol)

logger = logging.getLogger(__name__)


class KeyDBClient:
    """
    KeyDB client (Redis-compatible).
    Uses redis-py library which works with KeyDB's Redis protocol.
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 6379,
        password: str | None = None,
        db: int = 0,
        decode_responses: bool = True,
    ) -> None:
        """
        Args:
            host: KeyDB server host
            port: KeyDB server port
            password: Optional password
            db: Database number
            decode_responses: Decode responses as strings
        """
        self._host = host
        self._port = port
        self._client = redis.Redis(
            host=host,
            port=port,
            password=password,
            db=db,
            decode_responses=decode_responses,
            socket_connect_timeout=5,
            socket_timeout=5,
        )

    def ping(self) -> bool:
        """Check if KeyDB is available."""
        try:
            return self._client.ping()
        except Exception as e:
            logger.warning("KeyDB ping failed: %s", e)
            return False

    def set(
        self,
        key: str,
        value: str,
        ex: int | None = None,
        px: int | None = None,
    ) -> bool:
        """
        Set a key-value pair.

        Args:
            key: Key name
            value: Value string
            ex: Expiration time in seconds
            px: Expiration time in milliseconds

        Returns:
            True if successful
        """
        try:
            return self._client.set(key, value, ex=ex, px=px)
        except Exception as e:
            logger.warning("KeyDB set failed for key %s: %s", key, e)
            return False

    def get(self, key: str) -> str | None:
        """
        Get a value by key.

        Args:
            key: Key name

        Returns:
            Value string or None
        """
        try:
            return self._client.get(key)
        except Exception as e:
            logger.warning("KeyDB get failed for key %s: %s", key, e)
            return None

    def delete(self, *keys: str) -> int:
        """
        Delete one or more keys.

        Args:
            *keys: Key names

        Returns:
            Number of keys deleted
        """
        try:
            return self._client.delete(*keys)
        except Exception as e:
            logger.warning("KeyDB delete failed: %s", e)
            return 0

    def exists(self, *keys: str) -> int:
        """
        Check if keys exist.

        Args:
            *keys: Key names

        Returns:
            Number of keys that exist
        """
        try:
            return self._client.exists(*keys)
        except Exception as e:
            logger.warning("KeyDB exists check failed: %s", e)
            return 0

    def expire(self, key: str, time: int) -> bool:
        """
        Set expiration time for a key.

        Args:
            key: Key name
            time: Expiration time in seconds

        Returns:
            True if successful
        """
        try:
            return self._client.expire(key, time)
        except Exception as e:
            logger.warning("KeyDB expire failed for key %s: %s", key, e)
            return False

    def incr(self, key: str, amount: int = 1) -> int:
        """
        Increment a key's value.

        Args:
            key: Key name
            amount: Increment amount

        Returns:
            New value
        """
        try:
            return self._client.incr(key, amount)
        except Exception as e:
            logger.warning("KeyDB incr failed for key %s: %s", key, e)
            return 0

    def hset(self, name: str, key: str, value: str) -> int:
        """
        Set a field in a hash.

        Args:
            name: Hash name
            key: Field name
            value: Field value

        Returns:
            Number of fields added
        """
        try:
            return self._client.hset(name, key, value)
        except Exception as e:
            logger.warning("KeyDB hset failed for hash %s: %s", name, e)
            return 0

    def hget(self, name: str, key: str) -> str | None:
        """
        Get a field from a hash.

        Args:
            name: Hash name
            key: Field name

        Returns:
            Field value or None
        """
        try:
            return self._client.hget(name, key)
        except Exception as e:
            logger.warning("KeyDB hget failed for hash %s: %s", name, e)
            return None

    def hgetall(self, name: str) -> dict[str, str]:
        """
        Get all fields from a hash.

        Args:
            name: Hash name

        Returns:
            Dictionary of field-value pairs
        """
        try:
            return self._client.hgetall(name)
        except Exception as e:
            logger.warning("KeyDB hgetall failed for hash %s: %s", name, e)
            return {}

    def close(self) -> None:
        """Close the connection."""
        try:
            self._client.close()
        except Exception:
            pass
