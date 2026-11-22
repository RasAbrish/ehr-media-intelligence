# ADR-009: stdlib sqlite3 with repositories

- **Status:** Accepted
- **Date:** 2026-11-22

## Context

The system stores a small relational model, whole Bundles as JSON, caches and audit rows on one machine. Reviewers should be able to read every query.

## Decision

Use the standard library `sqlite3` with WAL, foreign keys and repository classes, plus a read model for the API. Every value is a `?` parameter, and sortable columns come from fixed whitelists.

## Alternatives rejected

- **SQLAlchemy ORM.** It adds mapping code and a dependency for a schema of 13 tables.
- **PostgreSQL.** It adds a service without a need at this size.

## Consequences

- The setup is one file with no service, and the SQL is explicit.
- There is no migration tool. The schema is applied idempotently, and a breaking change means rebuilding with `make pipeline`.
- Three small read-only statements sit outside the repositories, in the readiness check, the CLI and the evaluator.
- SQLite allows one writer at a time, so multi-replica production needs PostgreSQL.
