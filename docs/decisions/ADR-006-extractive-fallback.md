# ADR-006: Extractive fallback summarizer

- **Status:** Accepted
- **Date:** 2026-11-22

## Context

A reviewer may have no API key, and a model call can fail, be refused or hit the daily token budget. The pipeline and the interface still have to work.

## Decision

Provide a deterministic extractive provider. It uses section headings and a concept dictionary over the same de-identified text, returns the same schema and passes the same guardrails. It is the provider when there is no key and the fallback for each patient whose model call fails. The fallback reason is stored and shown.

## Alternatives rejected

- **Fail without a key.** The main feature could not be reviewed or tested offline.
- **A local language model.** It adds gigabytes of weights, slow summaries on a CPU and a second prompt to evaluate.

## Consequences

- Everything runs offline, and the test suite and `make eval` evaluate summaries without a key.
- Extractive summaries always report low confidence and read as extracted fragments.
- The dictionary limits recall: on the synthetic set it finds 84 of 96 expected conditions and misses all 6 expected cases of hyponatremia and 6 of the 12 of hyperlipidemia.
