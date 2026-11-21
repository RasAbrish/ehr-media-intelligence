"""Short-lived caches behind one protocol (docs/02 section 8, docs/07 section 6).

``MemoryBackend`` is the R tier. A Redis backend arrives in Phase 6; until then a
``CACHE_BACKEND=redis`` setting falls back to memory with a warning. Values are
bytes, keys are namespaced (``ehr-mip:…``), and a cache failure never fails a
request.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from typing import Literal, Protocol

import structlog
from cachetools import LRUCache

from ehr_mip.config import Settings

log = structlog.get_logger(__name__)
BackendName = Literal["memory", "redis"]
MAX_ENTRIES = 512


class CacheBackend(Protocol):
    @property
    def name(self) -> BackendName: ...

    async def get(self, key: str) -> bytes | None: ...

    async def set(self, key: str, value: bytes, ttl_s: int) -> None: ...

    async def incr_index_version(self) -> int: ...

    async def index_version(self) -> int: ...

    async def ping(self) -> bool: ...


class MemoryBackend:
    """In-process LRU (512 entries) with a TTL per entry."""

    name: BackendName = "memory"

    def __init__(
        self, maxsize: int = MAX_ENTRIES, clock: Callable[[], float] = time.monotonic
    ) -> None:
        self._entries: LRUCache[str, tuple[float, bytes]] = LRUCache(maxsize=maxsize)
        self._clock = clock
        self._lock = asyncio.Lock()
        self._version = 0

    async def get(self, key: str) -> bytes | None:
        async with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                return None
            expires, value = entry
            if expires <= self._clock():
                del self._entries[key]
                return None
            return value

    async def set(self, key: str, value: bytes, ttl_s: int) -> None:
        if ttl_s <= 0:
            return
        async with self._lock:
            self._entries[key] = (self._clock() + ttl_s, value)

    async def incr_index_version(self) -> int:
        async with self._lock:
            self._version += 1
            self._entries.clear()
            return self._version

    async def index_version(self) -> int:
        return self._version

    async def ping(self) -> bool:
        return True


async def safe_get(cache: CacheBackend, key: str) -> bytes | None:
    """``get`` that never fails a request: errors are logged and treated as a miss."""
    try:
        return await cache.get(key)
    except Exception as error:
        log.warning(
            "cache_error", operation="get", backend=cache.name, error_type=type(error).__name__
        )
        return None


async def safe_set(cache: CacheBackend, key: str, value: bytes, ttl_s: int) -> None:
    try:
        await cache.set(key, value, ttl_s)
    except Exception as error:
        log.warning(
            "cache_error", operation="set", backend=cache.name, error_type=type(error).__name__
        )


def build_cache(settings: Settings) -> CacheBackend:
    if settings.cache_backend == "redis":
        log.warning(
            "cache_backend_fallback",
            requested="redis",
            using="memory",
            reason="Redis backend arrives in Phase 6",
        )
    return MemoryBackend()
