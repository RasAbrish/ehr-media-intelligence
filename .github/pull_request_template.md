## Summary

<!-- What changed and why, in two or three sentences. -->

## Requirements

<!-- Requirement ids from docs/01-SPEC.md, for example FR-1.4, NFR-04. -->

## Evidence

- [ ] `make check` green (paste test counts and coverage)
- [ ] `make security` clean
- [ ] Contract snapshot test passes, or `docs/04-API-CONTRACT.md` was updated first
- [ ] Screenshots at 390, 1024 and 1440 px in light and dark (UI changes)

## Security and AI checklist

- [ ] Synthetic data only; no secrets added
- [ ] No PHI in logs or LLM prompts
- [ ] New endpoints have rate limits, input limits and problem+json errors
- [ ] Prompt changes use a new version folder and include `make eval` before and after
- [ ] Every new UI state (loading, empty, error, AI fallback) is designed and axe clean
