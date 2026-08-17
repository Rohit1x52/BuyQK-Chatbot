"""
This file will:
Connect FastAPI to Redis.
Provide a reusable Redis client.
Store temporary conversation state.
Store session data.
Support expiration/TTL.
Later support caching and rate limiting.
"""

import os
import json

import redis
from dotenv import load_dotenv


# Load environment variables from .env
load_dotenv()


# Redis connection settings
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_DB = int(os.getenv("REDIS_DB", 0))


# Create Redis client
redis_client = redis.Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    db=REDIS_DB,
    decode_responses=True
)


def get_redis():
    """
    Returns the Redis client.

    This can be used with FastAPI dependency injection.
    """

    return redis_client


def check_redis_connection():
    """
    Checks whether Redis is available.
    """

    try:
        return redis_client.ping()
    except redis.RedisError:
        return False


def set_value(key: str, value, expire: int | None = None):
    """
    Store a value in Redis.

    Args:
        key: Redis key.
        value: Value to store.
        expire: Expiration time in seconds.
    """

    if isinstance(value, (dict, list)):
        value = json.dumps(value)

    redis_client.set(
        key,
        value,
        ex=expire
    )


def get_value(key: str):
    """
    Retrieve a value from Redis.

    Automatically converts JSON strings back
    into Python dictionaries/lists when possible.
    """

    value = redis_client.get(key)

    if value is None:
        return None

    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return value


def delete_value(key: str):
    """
    Delete a value from Redis.
    """

    redis_client.delete(key)