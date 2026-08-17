# Purpose:
# Provides conversation memory for the BuyQK AI engine.
#
# MVP architecture:
#
# Application
#      ↓
# ConversationMemory
#      ↓
# ┌───────────────────────┐
# │ Redis available?      │
# └───────────┬───────────┘
#             │
#       ┌─────┴─────┐
#       │           │
#      YES          NO
#       │           │
#       ▼           ▼
#     Redis      In-memory
#
# Redis will eventually be used for persistent/shared
# conversation memory.
#
# The in-memory fallback is useful for:
# - Local development
# - Testing
# - Running BuyQK before Redis is installed/running
#
# IMPORTANT:
# This module stores conversation messages only.
# It does not store transactional database records.
#
# Orders, products, users, etc. remain in SQLite/PostgreSQL.


from __future__ import annotations

import json
from typing import Any


# =========================================================
# Optional Redis Import
# =========================================================
#
# Redis is treated as an infrastructure dependency.
#
# If redis-py is not installed, the application can still
# use the in-memory fallback.
# =========================================================

try:

    import redis

except ImportError:

    redis = None


# =========================================================
# In-Memory Fallback
# =========================================================

_MEMORY_STORE: dict[str, list[dict[str, Any]]] = {}


# =========================================================
# Conversation Memory
# =========================================================

class ConversationMemory:
    """
    Conversation memory abstraction.

    Redis is preferred when available.

    If Redis is unavailable, the class automatically falls
    back to local in-memory storage.

    Example:

        memory = ConversationMemory()

        memory.add_message(
            "session-123",
            "user",
            "Find Amul milk"
        )

        messages = memory.get_messages(
            "session-123"
        )
    """

    def __init__(
        self,
        redis_url: str = "redis://localhost:6379/0",
        ttl: int = 3600,
        max_messages: int = 20,
        use_fallback: bool = True,
    ):
        """
        Initialize conversation memory.

        Args:
            redis_url:
                Redis connection URL.

            ttl:
                Conversation expiration time in seconds.

            max_messages:
                Maximum number of messages retained
                per conversation.

            use_fallback:
                Whether to use in-memory storage when
                Redis is unavailable.
        """

        self.redis_url = redis_url

        self.ttl = ttl

        self.max_messages = max_messages

        self.use_fallback = use_fallback

        self.client = None

        self.redis_available = False

        self._connect()


    # =====================================================
    # Redis Connection
    # =====================================================

    def _connect(self) -> None:
        """
        Attempt to connect to Redis.

        Failure does not crash the application.
        """

        if redis is None:

            self.redis_available = False

            return

        try:

            self.client = redis.Redis.from_url(
                self.redis_url,
                decode_responses=True,
            )

            # -------------------------------------------------
            # Verify connection.
            # -------------------------------------------------

            self.client.ping()

            self.redis_available = True

        except Exception:

            self.client = None

            self.redis_available = False

            if not self.use_fallback:

                raise


    # =====================================================
    # Session Key
    # =====================================================

    def _get_key(
        self,
        session_id: str,
    ) -> str:
        """
        Generate a Redis key for a conversation.
        """

        return (
            f"buyqk:conversation:{session_id}"
        )


    # =====================================================
    # Add Message
    # =====================================================

    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """
        Store a conversation message.

        Args:
            session_id:
                Unique conversation identifier.

            role:
                Usually:
                - user
                - assistant
                - system

            content:
                Message text.

            metadata:
                Optional additional information.
        """

        if not session_id:

            raise ValueError(
                "session_id is required."
            )

        if not role:

            raise ValueError(
                "role is required."
            )

        if not content:

            raise ValueError(
                "content is required."
            )

        message = {
            "role": role,
            "content": content,
            "metadata": metadata or {},
        }

        # -----------------------------------------------------
        # Redis
        # -----------------------------------------------------

        if self.redis_available:

            key = self._get_key(
                session_id
            )

            try:

                self.client.rpush(
                    key,
                    json.dumps(message),
                )

                # Keep only the latest messages.
                self.client.ltrim(
                    key,
                    -self.max_messages,
                    -1,
                )

                self.client.expire(
                    key,
                    self.ttl,
                )

                return

            except Exception:

                # Redis may become unavailable after
                # initialization.
                self.redis_available = False

                self.client = None

                if not self.use_fallback:

                    raise

        # -----------------------------------------------------
        # In-memory fallback
        # -----------------------------------------------------

        if self.use_fallback:

            messages = _MEMORY_STORE.setdefault(
                session_id,
                [],
            )

            messages.append(
                message
            )

            # Keep only the latest messages.
            _MEMORY_STORE[
                session_id
            ] = messages[
                -self.max_messages:
            ]


    # =====================================================
    # Get Messages
    # =====================================================

    def get_messages(
        self,
        session_id: str,
    ) -> list[dict[str, Any]]:
        """
        Retrieve conversation history.

        Returns:
            List of conversation messages.
        """

        if not session_id:

            raise ValueError(
                "session_id is required."
            )

        # -----------------------------------------------------
        # Redis
        # -----------------------------------------------------

        if self.redis_available:

            key = self._get_key(
                session_id
            )

            try:

                raw_messages = self.client.lrange(
                    key,
                    0,
                    -1,
                )

                return [
                    json.loads(message)
                    for message in raw_messages
                ]

            except Exception:

                self.redis_available = False

                self.client = None

                if not self.use_fallback:

                    raise

        # -----------------------------------------------------
        # In-memory fallback
        # -----------------------------------------------------

        if self.use_fallback:

            return list(
                _MEMORY_STORE.get(
                    session_id,
                    [],
                )
            )

        return []


    # =====================================================
    # Get Recent Messages
    # =====================================================

    def get_recent_messages(
        self,
        session_id: str,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """
        Return only the most recent conversation messages.
        """

        messages = self.get_messages(
            session_id
        )

        return messages[
            -limit:
        ]


    # =====================================================
    # Clear Conversation
    # =====================================================

    def clear(
        self,
        session_id: str,
    ) -> None:
        """
        Delete conversation memory for a session.
        """

        if not session_id:

            raise ValueError(
                "session_id is required."
            )

        # -----------------------------------------------------
        # Redis
        # -----------------------------------------------------

        if self.redis_available:

            key = self._get_key(
                session_id
            )

            try:

                self.client.delete(
                    key
                )

            except Exception:

                self.redis_available = False

                self.client = None

                if not self.use_fallback:

                    raise

        # -----------------------------------------------------
        # In-memory fallback
        # -----------------------------------------------------

        _MEMORY_STORE.pop(
            session_id,
            None,
        )


    # =====================================================
    # Check Connection
    # =====================================================

    def is_available(self) -> bool:
        """
        Return whether Redis is currently available.
        """

        return self.redis_available


    # =====================================================
    # Memory Status
    # =====================================================

    def status(self) -> dict[str, Any]:
        """
        Return memory infrastructure status.
        """

        return {
            "redis_available": self.redis_available,
            "fallback_enabled": self.use_fallback,
            "max_messages": self.max_messages,
            "ttl": self.ttl,
        }


# =========================================================
# Default Memory Instance
# =========================================================

conversation_memory = ConversationMemory()