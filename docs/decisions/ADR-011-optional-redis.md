# ADR-011: Redis optional, in-memory TTL cache by default

- **Status:** Accepted
- **Date:** 2026-11-22

## Context

Search results and rate limit counters benefit from sharing only when several API processes run. The assessment runs one process on little data.

## Decision

Keep a memory TTL cache as the default behind `CacheBackend`. `CACHE_BACKEND` is `memory`, `redis` or `auto`. Compose uses `auto`: memory until Redis first answers, so the `redis` profile needs no other setting. After a failure each process caches and counts in memory for five seconds and tries again, and `/ready` reports degraded.

## Alternatives rejected

- **Redis required.** It is one more service for no gain with one process.
- **Failing requests when Redis is down.** A cache outage would become a search outage.

## Consequences

- A cache failure never fails a request.
- During an outage the rate limits are per process and therefore looser with several replicas.
- Search cache entries hold ids, scores and scrubbed snippets. Patient responses are never written to Redis.
