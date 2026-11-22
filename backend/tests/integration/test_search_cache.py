"""Search cache and rate limits on Redis (docs/02 section 8, docs/09 section 5.2, FR-9.1)."""

from __future__ import annotations

from contextlib import closing
from pathlib import Path

import fakeredis
import pytest
from fastapi.testclient import TestClient
from limits.aio.storage import MemoryStorage, RedisStorage
from tests.support.api import settings_for

from ehr_mip.api.main import create_app
from ehr_mip.api.rate_limit import RateLimitMiddleware, build_storage
from ehr_mip.cache.backend import FallbackCache, RedisBackend
from ehr_mip.db.connection import connect
from ehr_mip.search.embedder import HashEmbedder


def redis_client(root: Path, server: fakeredis.FakeServer) -> TestClient:
    app = create_app(
        settings_for(root),
        embedder_factory=lambda _: HashEmbedder(),
        cache=FallbackCache(RedisBackend(fakeredis.FakeAsyncRedis(server=server))),
        configure_logs=False,
    )
    return TestClient(app)


def test_search_cache_hits_on_redis_without_identifiers(api_store: Path) -> None:
    server = fakeredis.FakeServer()
    with redis_client(api_store, server) as client:
        first = client.post("/search", json={"query": "kidney disease"})
        again = client.post("/search", json={"query": "kidney disease"})
        key = first.json()["results"][0]["patient"]["patient_key"]
        client.get(f"/patients/{key}")
        ready = client.get("/ready").json()
    assert (first.headers["x-cache"], again.headers["x-cache"]) == ("MISS", "HIT")
    assert ready["flags"]["cache_backend"] == "redis"
    assert ready["cache"]["backend"] == "redis"
    assert ready["cache"]["ok"] is True

    reader = fakeredis.FakeRedis(server=server)
    keys = [k.decode() for k in reader.keys("*")]
    # Patient responses hold identifiers, so only search results reach Redis.
    assert keys
    assert all(k.startswith("ehr-mip:search:") for k in keys)
    stored = b" ".join(reader.get(k) for k in keys).decode()
    with closing(connect(api_store / "ehr.db")) as conn:
        patients = conn.execute("SELECT family_name, given_names, birth_date FROM patients")
        for family, _given, birth in patients:
            assert not birth or birth not in stored
            assert not family or f'"{family}"' not in stored


def test_search_works_when_redis_is_down(api_store: Path) -> None:
    server = fakeredis.FakeServer()
    server.connected = False
    with redis_client(api_store, server) as client:
        response = client.post("/search", json={"query": "kidney disease"})
        ready = client.get("/ready")
    assert response.status_code == 200
    body = ready.json()
    assert ready.status_code == 200  # degraded, never down
    assert body["status"] == "degraded"
    assert body["cache"] == {**body["cache"], "backend": "memory", "ok": False}


class BrokenStorage(MemoryStorage):
    async def incr(self, *args: object, **kwargs: object) -> int:
        raise ConnectionError


def limited(storage: MemoryStorage) -> TestClient:
    async def ok(scope: object, receive: object, send: object) -> None:
        await send({"type": "http.response.start", "status": 200, "headers": []})  # type: ignore[operator]
        await send({"type": "http.response.body", "body": b""})  # type: ignore[operator]

    return TestClient(RateLimitMiddleware(ok, storage=storage))  # type: ignore[arg-type]


def test_rate_limit_still_enforced_when_redis_fails() -> None:
    client = limited(BrokenStorage())
    codes = [client.post("/search").status_code for _ in range(61)]
    assert codes == [200] * 60 + [429]


@pytest.mark.parametrize(("backend", "kind"), [("memory", MemoryStorage), ("redis", RedisStorage)])
async def test_rate_limit_storage_follows_the_setting(
    api_store: Path, backend: str, kind: type
) -> None:
    assert isinstance(build_storage(settings_for(api_store, cache_backend=backend)), kind)


def test_rate_limit_uses_memory_until_auto_finds_redis() -> None:
    redis_up = False

    async def ok(scope: object, receive: object, send: object) -> None:
        await send({"type": "http.response.start", "status": 200, "headers": []})  # type: ignore[operator]
        await send({"type": "http.response.body", "body": b""})  # type: ignore[operator]

    class Counting(MemoryStorage):
        hits = 0

        async def incr(self, *args: object, **kwargs: object) -> int:
            type(self).hits += 1
            return await super().incr(*args, **kwargs)  # type: ignore[arg-type]

    client = TestClient(
        RateLimitMiddleware(ok, storage=Counting(), shared=lambda: redis_up)  # type: ignore[arg-type]
    )
    client.post("/search")
    assert Counting.hits == 0
    redis_up = True
    client.post("/search")
    assert Counting.hits == 1
