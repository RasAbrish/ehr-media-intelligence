# Architecture decision records

One file per decision: context, decision, alternatives rejected, consequences and status. The summary table lives in `docs/02-ARCHITECTURE.md` section 11.

- [ADR-001](ADR-001-fhir-resources-r4b.md): Use fhir.resources 8.x with the R4B sub-package
- [ADR-002](ADR-002-chromadb.md): Use ChromaDB as the vector store
- [ADR-003](ADR-003-result-unit-resource.md): Search result unit is one FHIR resource (best chunk)
- [ADR-004](ADR-004-uuidv5-ids.md): UUIDv5 ids from stable source facts
- [ADR-005](ADR-005-deidentified-llm-context.md): De-identified LLM context
- [ADR-006](ADR-006-extractive-fallback.md): Extractive fallback summarizer
- [ADR-007](ADR-007-conservative-identity.md): Conservative identity resolution
- [ADR-008](ADR-008-us-date-policy.md): Ambiguous dates parsed as US MM/DD with a warning audit
- [ADR-009](ADR-009-stdlib-sqlite.md): stdlib sqlite3 with repositories
- [ADR-010](ADR-010-tanstack-router.md): Use TanStack Router with validated search params
- [ADR-011](ADR-011-optional-redis.md): Redis optional, in-memory TTL cache by default
- [ADR-012](ADR-012-slowapi.md): Use the limits library for rate limiting
- [ADR-013](ADR-013-sessions.md): Server-side sessions with scrypt password hashes
- [ADR-014](ADR-014-groq-and-shipped-summaries.md): Optional Groq provider and summaries shipped as a file
