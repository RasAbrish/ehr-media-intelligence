# ADR-003: Search result unit is one FHIR resource (best chunk)

- **Status:** Accepted
- **Date:** 2026-11-22

## Context

The brief asks for matching patient records. Long notes are split into overlapping chunks for embedding, so raw vector hits can show the same note several times.

## Decision

One result is one FHIR resource, represented by its best chunk. Search fetches six candidates per requested result, keeps the best per resource (`search/ranking.py`), and returns the top results with that chunk's snippet, score and match type.

## Alternatives rejected

- **Raw chunks.** One long note could fill all five results.
- **One result per patient.** It hides which record matched, and a clinician needs the record.

## Consequences

- Every result opens a real record and can be cited by type and id.
- One patient can appear several times through different records.
- If many candidates belong to the same resource, a search can return fewer results than requested.
