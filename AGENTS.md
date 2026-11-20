# AGENTS.md

Operating manual for any coding agent working on **EHR Media Intelligence Platform** (Onye AI Full-stack Assessment).
Read this file, then the docs in order. Do not write code before reading `docs/01-SPEC.md` and `docs/02-ARCHITECTURE.md`.

## Document map

| File | Read when |
|---|---|
| `docs/01-SPEC.md` | Always first. Requirements with IDs (FR, NFR), scope tiers, acceptance criteria |
| `docs/02-ARCHITECTURE.md` | Before any code. System, container, component, sequence and deployment diagrams |
| `docs/03-DATA-MODEL.md` | Before touching models, SQLite, FHIR mapping or the vector index |
| `docs/04-API-CONTRACT.md` | Before touching any endpoint or any frontend data fetching. **The contract is law** |
| `docs/05-ALGORITHMS.md` | Before implementing cleaning, identity, dedupe, validation, summarization or ranking |
| `docs/06-UI-DESIGN.md` | Before any UI work. Tokens, components, layouts, accessibility |
| `docs/07-ENGINEERING-PRACTICES.md` | Coding standards, testing, CI, git rules |
| `docs/08-DELIVERY.md` | Phase plan, commit plan, write-up and final checklist |
| `docs/09-SECURITY.md` | Before any endpoint, middleware, logging, Docker or LLM work. Threat model and required controls |
| `docs/10-AI-DESIGN.md` | Before any summarization, prompt, eval or AI UI work. System card, safety, evaluation, AI UX |

## Golden rules

1. **Synthetic data only.** Never use real patient data or real names from public datasets.
2. **Follow the phase order in `08-DELIVERY.md`.** A phase starts only when the previous one meets its acceptance criteria.
3. **Contract first.** API changes start in `04-API-CONTRACT.md`, then Pydantic schemas, then Zod schemas, then code. Backend and frontend must match it field for field.
4. **Tests first** for cleaning rules, mappers, guardrails and filters.
5. **`make check` green before every commit.**
6. **Layering is strict:** `ingestion → fhir → summarization → search → api`. Lower layers never import higher ones. No business logic in routers or React components.
7. **No PHI in logs or LLM prompts.** Logs carry ids only. LLM context is de-identified.
8. **No secrets in git.** Every variable lives in `.env.example` with a comment.
9. **Verify current library APIs** before use (fhir.resources 8.x, chromadb 1.x, anthropic SDK, TanStack Query v5, TanStack Table v9, TanStack Router, shadcn CLI v4, Tailwind v4). Do not rely on memory.
10. **Security controls are requirements,** not polish: headers, rate limits, input limits, log redaction and container hardening from `09-SECURITY.md` ship with the phase that introduces the surface.
11. **Prompts are versioned files.** Never edit a released prompt version; create a new one and run `make eval` (`10-AI-DESIGN.md` section 3).
12. **Every UI state is designed.** Loading, empty, error, partial and AI-fallback states exist for every screen (`06-UI-DESIGN.md`).
13. **When a requirement is unclear,** check the traceability matrix in `01-SPEC.md` section 7. If still unclear, stop and ask.

## Commands (repo root)

| Command | Purpose |
|---|---|
| `make setup` | Install backend (uv) and frontend (pnpm) deps, pre-commit hooks |
| `make data` | Generate seeded synthetic raw data in `data/raw/` |
| `make pipeline` | ingest → normalize → summarize → index (idempotent) |
| `make api` / `make web` / `make dev` | Run API (:8000), web (:5173), or both |
| `make test` / `make e2e` | Unit and integration tests / Playwright |
| `make lint` / `make typecheck` / `make fmt` | Static checks and formatting |
| `make check` | lint + typecheck + test. Gate before commit |
| `make eval` | Summary quality report into `reports/` |
| `make openapi` | Export `docs/openapi.json` and run the contract snapshot test |
| `make writeup-pdf` | Render `docs/WRITEUP.md` to PDF |
| `make security` | pip-audit, pnpm audit, gitleaks, Trivy (if Docker available) |
| `make storybook` | Component workshop with a11y addon on :6006 |
| `make lighthouse` | Lighthouse CI against the built web app |
| `docker compose --profile redis up` | Run with Redis as cache and rate limit backend |

Backend CLI: `uv run ehr-mip {ingest|normalize|summarize|index|run-all|serve|eval}`.

## Definition of done (every phase)

1. Acceptance criteria from `01-SPEC.md` for the phase pass.
2. `make check` green, coverage not lower than before.
3. Contract snapshot test passes (or the contract doc was updated first).
4. `make security` clean (no high or critical findings).
5. New UI has Storybook stories for shared components and passes axe.
6. README section updated.
7. Squash commit on `main` with the planned message from `08-DELIVERY.md`.

## Writing style for README and write-up

Concise, direct, natural and professional. No em-dashes or dashes used to join clauses. No marketing tone. Write-up fits on one page.
