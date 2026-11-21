"""MemoryBackend: TTL per entry, LRU bound, index version (docs/07 section 6)."""

from __future__ import annotations

import pytest

from ehr_mip.cache.backend import MemoryBackend, build_cache
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


def test_redis_setting_falls_back_to_memory(caplog: pytest.LogCaptureFixture) -> None:
    cache = build_cache(Settings(_env_file=None, cache_backend="redis"))  # type: ignore[call-arg]
    assert cache.name == "memory"
