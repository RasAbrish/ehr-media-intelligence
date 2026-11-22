# ADR-008: Ambiguous dates parsed as US MM/DD with a warning audit

- **Status:** Accepted
- **Date:** 2026-11-22

## Context

The exports mix ISO, named-month and slash dates. A value such as 03/04/2025 has two valid readings, and the source is a US Epic export.

## Decision

Read an ambiguous `NN/NN/YYYY` as month and day, and record a `date.parse.us_ambiguous` warning. When the first part is above 12, read day and month with an info note. Impossible dates are rejected with an error and never repaired by guessing (`ingestion/cleaners/dates.py`).

## Alternatives rejected

- **A silent guess.** Nobody could find or check the affected records.
- **Rejecting every ambiguous date.** It would drop valid dates from many records and break date filters.

## Consequences

- Every guess appears in the audit log and on the data quality page.
- A feed from a day-first country would be read wrongly, with a warning. Supporting one needs a locale setting per source.
