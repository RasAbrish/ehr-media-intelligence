# ADR-014: Optional Groq provider and summaries shipped as a file

- **Status:** Accepted
- **Date:** 2026-11-23

## Context

The brief asks for the Claude API or the OpenAI API. The Claude integration is built and tested with a fake provider, but the trial account had no credit, so no real model summary could be made. The public demo must not hold a model key: anyone signed in could then spend it.

## Decision

- Add `GroqProvider`, an OpenAI-compatible client for Groq's free tier (default model `openai/gpt-oss-120b`), with the same prompt, structured JSON schema, guardrails, cache and extractive fallback as Claude. `LLM_PROVIDER=groq` selects it; `auto` prefers Claude, then Groq.
- Model summaries are generated on a developer machine, exported with `ehr-mip summaries export` to `data/summaries/`, and imported while the API image builds. An import only applies when the bundle hash still matches, so a changed dataset falls back to the offline summaries instead of showing stale text.
- For one bundle, a model summary is preferred over an offline one, whatever their dates.

## Alternatives rejected

- **The key on the public host.** It needs no new code path, but any signed-in visitor could use up the quota, and the image builds its summaries before any secret exists.
- **Hugging Face Inference.** Also free, but with smaller monthly credits and less dependable JSON output.

## Consequences

- The summaries on the demo come from an open-weights model, not Claude. The interface shows the model id on every summary.
- Groq's free tier allows about 200,000 tokens a day for this model. A full run of 60 patients fits; the cache makes a stopped run resume where it ended.
- The first Groq run failed 4 of 7 evaluation gates (`docs/eval/eval_report_groq.md`). Its summaries were shipped anyway so the demo shows real model output, and the gaps are stated in the README and the system card.
- Claude stays the first choice and needs only a key with credit.
