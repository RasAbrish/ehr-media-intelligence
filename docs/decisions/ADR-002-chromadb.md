# ADR-002: Use ChromaDB as the vector store

- **Status:** Accepted
- **Date:** 2026-11-22

## Context

Search must combine semantic similarity with filters on resource type, patient and an inclusive date range, keep its index between runs, and run without another service on a reviewer's machine.

## Decision

Use ChromaDB in-process through `PersistentClient`. Vectors come from the local all-MiniLM-L6-v2 embedder, never from Chroma. Filters become a metadata `where` clause, with dates stored as ordinals (`search/filters.py`). A reindex builds a second collection and renames it into place, so readers never see an empty index.

## Alternatives rejected

- **FAISS.** It has no metadata filtering or metadata persistence, so both would be written and tested here.
- **A Chroma server.** It adds a service and a port, and the known server advisories would then apply.

## Consequences

- Filters apply inside the vector query, so a narrow filter still returns matches.
- Four advisories against the Chroma server are accepted in `docs/09-SECURITY.md` section 8.1, on the condition that no server is ever started. A test guards that condition.
- The wheel bundles its own SQLite, which the image scan cannot see.
- One process owns the index. Several API replicas would need a different store or a shared server.
