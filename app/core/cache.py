"""Redis cache helpers used by every LLM call.

Falls back to an in-memory dict if Redis is unreachable, so module
owners can develop without docker-compose running. Logs a warning
on fallback so it never silently masks a production issue.
"""
from __future__ import annotations

import logging
import time
from functools import wraps
from typing import Any, Callable, Optional

import redis

from app.core.config import get_settings

log = logging.getLogger(__name__)

_settings = get_settings()
_client: Optional[redis.Redis] = None
_memory_store: dict[str, tuple[str, float]] = {}  # key -> (value, expires_at)


def _get_client() -> Optional[redis.Redis]:
    """Lazy connect. None if Redis unavailable."""
    global _client
    if _client is not None:
        return _client
    try:
        c = redis.from_url(_settings.redis_url, decode_responses=True, socket_timeout=2)
        c.ping()
        _client = c
        log.info("Redis connected: %s", _settings.redis_url)
        return _client
    except Exception as e:
        log.warning("Redis unavailable (%s). Falling back to in-memory cache.", e)
        return None


def cache_get(key: str) -> Optional[str]:
    c = _get_client()
    if c is not None:
        try:
            return c.get(key)
        except Exception as e:
            log.warning("Redis GET failed for %s: %s", key, e)
    # memory fallback
    entry = _memory_store.get(key)
    if entry is None:
        return None
    value, expires_at = entry
    if expires_at < time.time():
        _memory_store.pop(key, None)
        return None
    return value


def cache_set(key: str, value: str, ttl: Optional[int] = None) -> None:
    ttl = ttl or _settings.default_cache_ttl_seconds
    c = _get_client()
    if c is not None:
        try:
            c.setex(key, ttl, value)
            return
        except Exception as e:
            log.warning("Redis SET failed for %s: %s", key, e)
    _memory_store[key] = (value, time.time() + ttl)


def cache_invalidate(key: str) -> None:
    c = _get_client()
    if c is not None:
        try:
            c.delete(key)
        except Exception as e:
            log.warning("Redis DELETE failed for %s: %s", key, e)
    _memory_store.pop(key, None)


def cached(ttl: Optional[int] = None, key_fn: Optional[Callable[..., str]] = None):
    """Decorator for caching arbitrary function results by computed key.

    Usage:
        @cached(ttl=86400, key_fn=lambda cid, jid: f"explain:{cid}:{jid}:v1")
        def generate(candidate_id, job_id): ...
    """
    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if key_fn is None:
                raise ValueError("cached() requires a key_fn")
            key = key_fn(*args, **kwargs)
            hit = cache_get(key)
            if hit is not None:
                return hit
            result = fn(*args, **kwargs)
            cache_set(key, result if isinstance(result, str) else str(result), ttl=ttl)
            return result
        return wrapper
    return decorator
