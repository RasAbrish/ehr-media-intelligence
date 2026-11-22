# ADR-004: UUIDv5 ids from stable source facts

- **Status:** Accepted
- **Date:** 2026-11-22

## Context

The pipeline is run repeatedly over the same exports. FHIR ids, summary cache entries, vector ids and feedback must point at the same thing after every run.

## Decision

Derive every key with UUIDv5 in one fixed namespace (`ids.py`) from source facts: patient from the MRN, encounter from patient and source id, document from patient and content hash, report and result from their source identifiers.

## Alternatives rejected

- **`uuid4`.** Every run would mint new ids, break the caches and duplicate rows.
- **Source ids as FHIR ids.** They repeat across files, are sometimes missing and can contain an MRN.

## Consequences

- A second run is idempotent and gives identical bundle hashes.
- The namespace can never change without rebuilding every store.
- An edit to a document's content, or a change of a patient's primary MRN, changes the key. Anything stored under the old key, such as feedback, no longer links to it.
- The ids are pseudonymous and not secret: anyone who knows an MRN and the namespace can recompute a patient key.
