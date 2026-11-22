# ADR-005: De-identified LLM context

- **Status:** Accepted
- **Date:** 2026-11-22

## Context

Summaries may be written by an external model. A whole FHIR Bundle would send name, MRN, birth date, phone and address, cost more tokens and give the model more to repeat wrongly.

## Decision

Send a purpose-built context (`summarization/context.py`): age, sex, record text, lab lines and rule anomalies, newest first, within a budget of about 6,000 tokens. The patient's name parts, MRN forms and birth date forms are replaced in free text, along with US phone numbers, street addresses, email addresses and SSN-shaped numbers. Author fields are not included, and instruction-like text is removed.

## Alternatives rejected

- **The whole Bundle.** It exposes identifiers and spends the budget on structure.
- **A statistical de-identification model.** It is a heavy dependency that still needs evaluation, and more than synthetic data requires.

## Consequences

- A test asserts that no synthetic patient's identifiers reach the context. The extractive provider reads the same scrubbed text.
- This is not HIPAA Safe Harbor de-identification. Record dates are kept, ages over 89 are not grouped, and the names of other people written inside note text are not detected.
- Records beyond the budget are left out, so a summary can miss older facts.
