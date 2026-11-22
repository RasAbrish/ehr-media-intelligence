"""Cache backends: one suite for memory and Redis, and Redis failure (docs/07 section 6)."""

from __future__ import annotations

import fakeredis
import pytest

from ehr_mip.cache.backend import (
    RETRY_AFTER_S,
    CacheBackend,
    FallbackCache,
    MemoryBackend,
    RedisBackend,
    build_cache,
)
from ehr_mip.config import Settings


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


async def test_get_set_and_expiry() -> None:
    clock = Clock()
    cache = MemoryBackend(clock=clock)
    assert await cache.get("k") is None
    await cache.set("k", b"v", ttl_s=60)
    assert await cache.get("k") == b"v"
    clock.now += 59
    assert await cache.get("k") == b"v"
    clock.now += 1
    assert await cache.get("k") is None
    await cache.set("off", b"v", ttl_s=0)  # TTL 0 disables caching
    assert await cache.get("off") is None
    assert await cache.ping()


async def test_lru_bound_and_index_version() -> None:
    cache = MemoryBackend(maxsize=2)
    for key in ("a", "b", "c"):
        await cache.set(key, key.encode(), ttl_s=60)
    assert await cache.get("a") is None  # evicted
    assert await cache.get("c") == b"c"
    assert await cache.index_version() == 0
    assert await cache.incr_index_version() == 1
    assert await cache.get("c") is None  # a version bump clears entries


@pytest.fixture(params=["memory", "redis"])
def backend(request: pytest.FixtureRequest) -> CacheBackend:
    if request.param == "memory":
        return MemoryBackend()
    return RedisBackend(fakeredis.FakeAsyncRedis())


async def test_backends_share_behavior(backend: CacheBackend) -> None:
    assert await backend.get("ehr-mip:search:1:k") is None
    await backend.set("ehr-mip:search:1:k", b"\x00value", ttl_s=60)
    assert await backend.get("ehr-mip:search:1:k") == b"\x00value"
    await backend.set("ehr-mip:off", b"v", ttl_s=0)  # TTL 0 disables caching
    assert await backend.get("ehr-mip:off") is None
    assert await backend.index_version() == 0
    assert await backend.incr_index_version() == 1
    assert await backend.index_version() == 1
    assert await backend.ping()
    await backend.aclose()


async def test_redis_values_expire() -> None:
    client = fakeredis.FakeAsyncRedis()
    await RedisBackend(client).set("ehr-mip:k", b"v", ttl_s=60)
    assert 0 < await client.ttl("ehr-mip:k") <= 60


async def test_redis_failure_falls_back_to_uncached() -> None:
    server = fakeredis.FakeServer()
    clock = Clock()
    failures: list[str] = []
    cache = FallbackCache(
        RedisBackend(fakeredis.FakeAsyncRedis(server=server)),
        clock=clock,
        on_error=lambda: failures.append("cache"),
    )
    await cache.set("k", b"redis", ttl_s=60)
    assert (cache.name, await cache.get("k")) == ("redis", b"redis")

    server.connected = False
    assert await cache.get("k") is None  # the failing request goes on uncached
    assert (cache.name, failures) == ("memory", ["cache"])
    await cache.set("k", b"memory", ttl_s=60)  # until the retry, memory serves
    assert await cache.get("k") == b"memory"
    assert failures == ["cache"]  # Redis is not hammered while it is down
    assert not await cache.ping()

    server.connected = True
    clock.now += RETRY_AFTER_S
    assert await cache.get("k") == b"redis"
    assert cache.name == "redis"
    assert await cache.ping()


async def test_redis_failure_on_write_never_raises() -> None:
    server = fakeredis.FakeServer()
    server.connected = False
    cache = FallbackCache(RedisBackend(fakeredis.FakeAsyncRedis(server=server)))
    await cache.set("k", b"v", ttl_s=60)
    assert cache.name == "memory"


def test_build_cache_follows_the_setting() -> None:
    memory = build_cache(Settings(_env_file=None))  # type: ignore[call-arg]
    assert isinstance(memory, MemoryBackend)
    redis = build_cache(Settings(_env_file=None, cache_backend="redis"))  # type: ignore[call-arg]
    assert isinstance(redis, FallbackCache)
    assert redis.name == "redis"


async def test_auto_follows_redis_while_running() -> None:
    """Compose sets auto: `--profile redis up` after a plain `up` keeps the API container."""
    server = fakeredis.FakeServer()
    server.connected = False
    clock = Clock()
    failures: list[str] = []
    cache = FallbackCache(
        RedisBackend(fakeredis.FakeAsyncRedis(server=server)),
        optional=True,
        clock=clock,
        on_error=lambda: failures.append("cache"),
    )
    await cache.set("k", b"memory", ttl_s=60)
    assert await cache.get("k") == b"memory"
    assert await cache.ping()  # no Redis was promised, so nothing is degraded
    assert (cache.name, failures) == ("memory", [])

    server.connected = True
    assert await cache.ping()
    assert cache.name == "redis"

    server.connected = False
    assert not await cache.ping()  # seen, then lost: an outage
    assert (cache.name, failures) == ("memory", ["cache"])


def test_build_cache_auto_starts_on_memory() -> None:
    cache = build_cache(Settings(_env_file=None, cache_backend="auto"))  # type: ignore[call-arg]
    assert isinstance(cache, FallbackCache)
    assert cache.name == "memory"
