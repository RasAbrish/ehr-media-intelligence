# Changelog

All notable changes to this project are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses one entry per delivery phase.

## [Unreleased]

### Added
- Sign-in with email and password: server-side sessions in an `HttpOnly` cookie, scrypt password hashes, a CSRF header on every POST, a login rate limit, `ehr-mip users add` and `users disable`, and a sign-in page with a public-domain photo. Every data route now needs a session (`docs/04` section 3a, ADR-013).
- A free public demo deployment: `render.yaml`, an index built into the API image, a demo banner that also covers cold starts, and `docs/DEPLOY.md`.

### Changed
- The top navigation is a sidebar with icons and labels that opens, closes and remembers the choice. Phones keep a menu.
- Content fills the screen from 320 to 2560 px. Tables become labeled cards in narrow containers, text in cards and the drawer wraps, and type scales on screens of 1920 px and wider.
- GitHub Actions is switched off because no hosted runner is available. The README, write-up and docs/07, 09 and 10 now say that the gates run by hand, and no longer claim an automated container hardening check.

### Fixed
- The extractive overview stated suspected diagnoses as fact (6 of 60 patients). It now says suspected, the summary cache key carries the rules version, and the manual review sheet shows each diagnosis status. Run `make pipeline` on an existing database.
- The scheduled eval workflow failed on every run: a fresh runner has no bundles, so it now runs ingest and normalize before eval.

## Phase 7

### Added
- Architecture decision records 002 to 012, the AI system card, the heuristic review, the restructured README with screenshots and Lighthouse scores, and the one-page write-up with `make writeup-pdf`.
- `sort=newest` on `POST /search` and a Sort by control: the most recent records with every search word, from the whole index, without AI summaries.
- Tests that keep the deliverable documents complete, and browser regressions for the review findings.

### Fixed
- Heuristic review, six findings of severity 3: the drawer lost the patient header, the FHIR JSON pane could not be scrolled by keyboard, records were truncated on phones, audit values wrapped one letter per line, Retry covered error text, and control borders were below 3:1 contrast.

### Changed
- `docs/01`, `docs/04`, `docs/05`, `docs/06`: the newest order. `SearchResponse` gains the required field `sort`.
- `docs/02`: ADR-010 and ADR-012 now describe what was built (`limits` instead of slowapi). `docs/06`: the `--input-border` token and the evidence chip's accessible name. `docs/08`: the PDF renderer. `docs/09`: the limits of de-identification.

### Removed
- The "not built yet" exit path of the CLI and its skip in the eval workflow, which would have passed a run that exited with code 3.

## Phase 6

### Added
- Phase 6, P1 features: hybrid search by default, hover prefetch, summary feedback with a confidence popover, the data quality page and drawer tab, the patient directory, `/stats`, the shortcuts dialog and first-run tip, Storybook coverage with an axe sweep, route-level code splitting with a 250 KB budget and Lighthouse CI.
- Redis cache and rate limit storage behind `CACHE_BACKEND` (`memory`, `redis`, `auto`) with fallback to memory, `AUTO_BOOTSTRAP`, hardened API and web images, Docker Compose with a redis profile, Trivy scans, CycloneDX SBOMs and the CI jobs for them.

### Fixed
- `make setup` failed on a clean clone: pnpm 12 rejects an undecided esbuild install script. The script is now explicitly denied.
- `.env.example` made Docker Compose read a comment as `ANTHROPIC_API_KEY`.
- The server access log printed query strings. It is off, and nginx no longer logs them.
- Phase 5 defects: filter popovers had no accessible name, calendar day labels failed label in name, the calendar ignored the design tokens, many hit targets were below 32 and 44 px, the card title had no tooltip, and Forward left the search box empty. Several review fixes reported in Phase 5 had no test and now have one.

### Changed
- `docs/04`: `cache_errors_total`, and 404 for feedback when `FEEDBACK_ENABLED=false`. `docs/06`: fallback reason in the provenance, and the light `--destructive` token darkened to 0.53 for AA contrast. `docs/07`: hybrid default and the `auto` cache backend. `docs/09`: the web container needs no added capability.
- `make e2e` starts its own servers on a copy of the data instead of reusing `make dev`.
- Gate policy, decided by the owner: Lighthouse gates at 4x CPU slowdown without network throttling and only reports slow 4G (`docs/01`, `docs/06`). Twelve Debian advisories without a fix are accepted until 2026-12-22, and CI now fails on any other high finding as well as critical ones (`docs/01`, `docs/09`).
- The first paint loads one app bundle instead of 11 files (239.5 KB gzip), and size-limit fails if the initial bundle splits again.

## Phase 5

### Added
- Phase 5, clinician UI (Task 5): live search with debounce and stale-while-refetching results, result cards with highlights and "why this result", type and date range filters in the URL, the patient drawer with the AI summary panel (disclaimer, provenance, suspected and data quality markers, confidence) and the linked records table (TanStack Table v9) with a record dialog; loading, idle, no results, error and index-empty states; the keyboard model, responsive layouts and light and dark themes. Zod schemas for the whole contract with a fixture test over every docs/04 example, MSW component tests, Storybook stories, and Playwright end-to-end tests with axe.

### Changed
- `docs/04`: no changes. Frontend tooling: Storybook 10, MSW 3 and Playwright added; the shadcn `calendar` and `scroll-area` files were removed instead of edited because they do not compile under the strict TypeScript settings; a themed `RangeCalendar` on react-day-picker replaces the calendar.

## Phase 4

### Added
- Phase 4, search and API (Task 4): chunker with identifier scrubbing, all-MiniLM-L6-v2 embeddings in an in-process Chroma collection, semantic and hybrid (BM25 with reciprocal rank fusion) ranking, MRN lookup, snippets and highlights; `ehr-mip index`, `run-all` and `serve`; the FastAPI app with `/health`, `/ready`, `POST /search`, patient detail, resources and summary (ETag), resource detail and `/metrics`; RFC 9457 problems, security headers, rate limits with `RateLimit-*` headers, body limit, PHI log redaction; a memory cache with index versioning; contract snapshot, security and latency tests.

### Changed
- `docs/02`: `index_version` is the count of finished index runs in SQLite. `docs/03`: summary chunks are dated by the newest record they cover. `docs/04`: `method_not_allowed` error code. `docs/09`: rate limiting uses the `limits` library directly and trusts `X-Forwarded-For` only from `FORWARDED_ALLOW_IPS`.

## Phase 3

### Added
- Phase 3, clinical summaries (Task 3): Fake, extractive and Anthropic providers behind one interface; de-identified, injection-scrubbed context; versioned prompts with a snapshot test; guardrails for grounding, diagnosis support, high anomaly restoration, field limits and the 200-word limit; computed confidence; a content-addressed summary cache; `llm_calls` telemetry with cost estimates and a daily token budget guard; golden and adversarial fixture sets; `ehr-mip summarize` and `ehr-mip eval` with JSON and Markdown reports and a manual review sheet. All offline eval gates pass.

### Changed
- `docs/05` and `docs/10`: no sampling parameters, `max_tokens` 4000 with effort `low`, refusal falls back to extractive, free-text scrubbing of contact details, negation-aware extractive diagnoses, and a trim that always ends at 200 words.
- `MediaRecord.kind` documented as `imaging | lab | pathology | note` in `docs/03`.

## Phase 2

### Added
- Phase 2, FHIR normalization (Task 2): mappers for Patient, Encounter, DocumentReference, DiagnosticReport (LAB, RAD, PAT) and Observation; one deterministic collection Bundle per patient with `bundle_hash`; schema and business-rule validation including value sets the library does not enforce; JSON and Markdown validation reports; the bundle store with a per-resource index; and `ehr-mip normalize`. All 60 synthetic bundles validate with zero errors.
- ADR-001 written up (FHIR R4 through the `fhir.resources` R4B package).

### Changed
- MRN identifier system is now `urn:oid:2.999.1.1` (the ITU-T example arc) in the data model and API contract, matching the generator.
- Clean patients keep a generational name suffix (`name_suffix`), mapped to `Patient.name.suffix`.

## Phase 1

### Added
- Phase 1, ingestion and cleaning (Task 1): JSON, CSV and TXT readers confined to the raw folder; cleaners for dates, gender, MRN, names, text, document type and lab values with recomputed flags; conservative identity resolution with MRN merges and flagged conflicts; exact, near and lab deduplication; a per-field audit log and quarantine; the SQLite schema and repository; and `ehr-mip ingest` with a stats table. Results match the synthetic ground truth exactly.

### Changed
- Phase 1 rule details recorded in `docs/05` section 1: extended document type keywords, scanned documents compatible with any type for near duplicates, a critical value table with its own `lab.flag_critical` rule, quarantine reason codes, and distinct keys for split patients who share a DOB.
- Key helpers moved to the shared `ehr_mip.ids` module (`docs/03` section 3.2).

## Phase 0

### Added
- Phase 0: monorepo scaffold with a uv backend (`ehr_mip`, layered packages, typed settings, Typer CLI) and a Vite React frontend (Tailwind v4, shadcn/ui on Base UI, TanStack Router and Query).
- Design tokens from `docs/06-UI-DESIGN.md` and a themed AppShell (light, dark, system) with responsive navigation and the index-empty state.
- Seeded synthetic EHR generator: 60 patients, about 250 records in JSON, CSV and TXT, every injected issue recorded in `_ground_truth.json`, and a planted prompt injection note.
- Makefile with `help`, pre-commit hooks (ruff, mypy, ESLint, Prettier, gitleaks, commitlint), CI and security workflows with SHA-pinned actions, Dependabot, PR and issue templates, CODEOWNERS, `SECURITY.md` and ADR stubs.

### Changed
- `SEARCH_MODE` defaults to `semantic` until hybrid search ships in Phase 6 (`docs/07` section 1.2).
- Root font size stays at the browser default and radius tokens map to component roles (`docs/06` section 10).

### Security
- Accepted four ChromaDB server advisories that do not apply to the embedded client (`docs/09` section 8.1).
