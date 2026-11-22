"""Short-lived caches behind one protocol (docs/02 section 8, docs/07 section 6).

``CACHE_BACKEND`` picks memory (default) or Redis. Redis is wrapped in
``FallbackCache``: the request that hits a failure goes on uncached, the process
serves from memory for a few seconds, then Redis is tried again. Values are bytes,
keys are namespaced (``ehr-mip:…``), and a cache failure never fails a request.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Literal, Protocol, TypeVar, cast

import structlog
from cachetools import LRUCache

from ehr_mip.config import Settings

if TYPE_CHECKING:
    from redis.asyncio import Redis

log = structlog.get_logger(__name__)
BackendName = Literal["memory", "redis"]
MAX_ENTRIES = 512
RETRY_AFTER_S = 5.0
REDIS_TIMEOUT_S = 0.25  # a search must not wait on a cache
_VERSION_KEY = "ehr-mip:index_version"
T = TypeVar("T")


class CacheBackend(Protocol):
    @property
    def name(self) -> BackendName: ...

    async def get(self, key: str) -> bytes | None: ...

    async def set(self, key: str, value: bytes, ttl_s: int) -> None: ...

    async def incr_index_version(self) -> int: ...

    async def index_version(self) -> int: ...

    async def ping(self) -> bool: ...

    async def aclose(self) -> None: ...


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

    async def aclose(self) -> None:
        """Nothing to release."""


class RedisBackend:
    """Shared cache on Redis. Errors propagate: ``FallbackCache`` handles them."""

    name: BackendName = "redis"

    def __init__(self, client: Redis) -> None:
        self._client = client

    async def get(self, key: str) -> bytes | None:
        return cast("bytes | None", await self._client.get(key))

    async def set(self, key: str, value: bytes, ttl_s: int) -> None:
        if ttl_s > 0:
            await self._client.set(key, value, ex=ttl_s)

    async def incr_index_version(self) -> int:
        return int(await self._client.incr(_VERSION_KEY))

    async def index_version(self) -> int:
        return int(await self._client.get(_VERSION_KEY) or 0)

    async def ping(self) -> bool:
        return bool(await self._client.ping())

    async def aclose(self) -> None:
        await self._client.aclose()


class FallbackCache:
    """Redis while it answers, this process's memory while it does not (docs/04 section 4.2).

    ``optional`` is ``CACHE_BACKEND=auto``: memory until Redis first answers, without
    errors, so the compose profile can start Redis under a running API. Once seen,
    losing Redis is an outage like any other.
    """

    def __init__(
        self,
        primary: CacheBackend,
        *,
        optional: bool = False,
        clock: Callable[[], float] = time.monotonic,
        on_error: Callable[[], None] = lambda: None,
    ) -> None:
        self._primary = primary
        self._memory = MemoryBackend(clock=clock)
        self._clock = clock
        self._on_error = on_error
        self._expected = not optional
        self._down_until: float | None = 0.0 if optional else None

    @property
    def name(self) -> BackendName:
        return self._primary.name if self._down_until is None else self._memory.name

    def _failed(self, operation: str, error: Exception) -> None:
        self._down_until = self._clock() + RETRY_AFTER_S
        if not self._expected:
            return
        self._on_error()
        log.warning(
            "cache_error", operation=operation, backend="redis", error_type=type(error).__name__
        )

    def _found(self) -> None:
        if not self._expected:
            log.info("cache_backend_selected", backend="redis")
        self._expected = True
        self._down_until = None

    async def _run(
        self, operation: str, call: Callable[[CacheBackend], Awaitable[T]], uncached: T
    ) -> T:
        if self._down_until is not None and self._clock() < self._down_until:
            return await call(self._memory)
        try:
            result = await call(self._primary)
        except Exception as error:
            self._failed(operation, error)
            return uncached if self._expected else await call(self._memory)
        self._found()
        return result

    async def get(self, key: str) -> bytes | None:
        return await self._run("get", lambda cache: cache.get(key), None)

    async def set(self, key: str, value: bytes, ttl_s: int) -> None:
        await self._run("set", lambda cache: cache.set(key, value, ttl_s), None)

    async def incr_index_version(self) -> int:
        return await self._run("incr", lambda cache: cache.incr_index_version(), 0)

    async def index_version(self) -> int:
        return await self._run("version", lambda cache: cache.index_version(), 0)

    async def ping(self) -> bool:
        """Health of Redis itself, so an outage shows in ``/ready`` as degraded."""
        try:
            healthy = await self._primary.ping()
        except Exception as error:
            self._failed("ping", error)
            return not self._expected
        if healthy:
            self._found()
        else:
            self._down_until = self._clock() + RETRY_AFTER_S
        return healthy or not self._expected

    async def aclose(self) -> None:
        try:
            await self._primary.aclose()
        except Exception as error:
            log.warning("cache_close_failed", error_type=type(error).__name__)


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


def build_cache(settings: Settings, on_error: Callable[[], None] = lambda: None) -> CacheBackend:
    """The configured backend. Nothing connects here: the first call or ping does."""
    if settings.cache_backend == "memory":
        return MemoryBackend()
    try:
        from redis.asyncio import Redis  # noqa: PLC0415 (optional extra)
    except ImportError:
        log.warning(
            "cache_backend_fallback",
            requested="redis",
            using="memory",
            reason="the redis extra is not installed",
        )
        return MemoryBackend()
    client = Redis.from_url(
        settings.redis_url,
        socket_timeout=REDIS_TIMEOUT_S,
        socket_connect_timeout=REDIS_TIMEOUT_S,
    )
    return FallbackCache(
        RedisBackend(client), optional=settings.cache_backend == "auto", on_error=on_error
    )
