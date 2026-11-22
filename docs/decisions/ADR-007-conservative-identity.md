# ADR-007: Conservative identity resolution

- **Status:** Accepted
- **Date:** 2026-11-22

## Context

The exports spell names differently, format MRNs differently, omit fields and reuse or change MRNs. A wrong merge shows one patient's history as another's. A missed merge only splits a history.

## Decision

Merge conservatively (`ingestion/identity.py`). Records with one MRN are one person when birth dates agree or one is missing and the name similarity is at least 90. Otherwise they are split and every side is flagged as a conflict. Different MRNs merge only on exact normalized family name, first given name and birth date, and the merge is audited.

## Alternatives rejected

- **Fuzzy merging across MRNs.** Twins, relatives and common names make it dangerous.
- **MRN alone.** It merges two people whenever an MRN is mistyped or reused.

## Consequences

- Conflicts and merges are visible in the directory, the drawer and the audit log.
- A misspelled name under a second MRN stays a separate patient until someone resolves it.
- Two different people with the same name and birth date under different MRNs would still merge. Production needs more identifiers and a review queue.
