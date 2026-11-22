# ADR-012: Use the limits library for rate limiting

- **Status:** Accepted
- **Date:** 2026-11-22

## Context

The API needs a limit per client and route group, with `RateLimit-*` headers, `Retry-After` and shared counters when Redis is present. slowapi was the planned choice, but it emits `X-RateLimit-*` headers, which the contract does not use.

## Decision

Call `limits`, the engine inside slowapi, directly from an ASGI middleware (`api/rate_limit.py`) with its async memory and Redis storages and a fixed window. The client address comes from `X-Forwarded-For` only when the peer is a trusted proxy.

## Alternatives rejected

- **slowapi.** Its headers do not match the contract.
- **Hand-written counters.** Windows, expiry and atomic Redis increments are solved in the library.

## Consequences

- Headers and the 429 problem document match `docs/04-API-CONTRACT.md`.
- A fixed window allows a short burst of up to twice the limit at a window boundary.
- `slowapi` is still declared in `pyproject.toml` because it was in the planned stack. No code imports it.
- Limits are per IP address, so clients behind one NAT share a bucket until authentication exists.
