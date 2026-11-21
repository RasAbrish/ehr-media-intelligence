# EHR Media Intelligence Platform

An AI pipeline that ingests raw EHR exports, cleans and normalizes them to HL7 FHIR R4, writes grounded clinical summaries with Claude and gives clinicians a fast semantic search interface. Built for the Onye AI full-stack assessment. All data is synthetic.

> Status: Phase 5 (clinician UI). Plus features and Docker arrive in Phase 6; see [docs/08-DELIVERY.md](docs/08-DELIVERY.md).

## Quick start

Requirements: Python 3.12, [uv](https://docs.astral.sh/uv/), Node 20.11 or newer, pnpm, git. Docker is needed from Phase 6.

```bash
make setup     # backend (uv) and frontend (pnpm) dependencies, git hooks
make data      # regenerate the seeded synthetic data in data/raw/
make check     # lint, type check and tests for backend and frontend
make ingest    # read, clean, resolve identities and dedupe into SQLite
make normalize # one validated FHIR R4 bundle per patient, plus the validation report
make summarize # one grounded summary per patient (extractive without an API key)
make index     # chunk, embed and index records and summaries
make pipeline  # all four stages in order (idempotent)
make api       # API on http://localhost:8000 (docs at /docs)
make dev       # API and web app together; open http://localhost:5173
```

`make` on its own lists every target. Targets for later phases exist already and print which phase delivers them.

Copy `.env.example` to `.env` to change settings. Nothing is required: without `ANTHROPIC_API_KEY` the system uses the extractive summarizer.

## Synthetic data

`scripts/generate_synthetic_data.py` builds 60 fictional patients with about 250 clinical records across three formats, seeded for byte-identical output:

| File | Content |
|---|---|
| `data/raw/ehr_export.json` | Patients, encounters and clinical documents (Epic-style export) |
| `data/raw/lab_results.csv` | Lab panels with LOINC codes and reference ranges |
| `data/raw/notes/*.txt` | Scanned reports and notes with a text header |
| `data/raw/_ground_truth.json` | Every injected issue with its location, for tests and evaluation only |

The generator injects the issues the pipeline must handle: mixed and ambiguous date formats, invalid dates, gender code variants, MRN and name format variants, missing fields, exact and near duplicates, one person registered under two MRNs (3 cases), one MRN shared by two people (2 cases), text noise, wrong or missing lab flags, unusable records, and one note with a planted prompt injection next to abnormal findings. Names come from Faker, phone numbers use the reserved 555-01xx range and the MRN system uses the ITU example OID arc `2.999`.

`make data` regenerates the files; CI fails if the committed data and the generator drift apart.

## Ingestion and cleaning (Task 1)

`make ingest` (`ehr-mip ingest`) reads the three raw formats, cleans every field, resolves patient identities, removes duplicates and writes the result to `data/generated/ehr_mip.db`. It prints a summary:

| Measure | Seed 42 |
|---|---|
| Records read (JSON, CSV, TXT) | 249, 292, 81 |
| Patients | 60 |
| Encounters, documents, lab results | 97, 150, 291 |
| Exact and near duplicates removed | 12, 7 |
| Identities merged (one person, two MRNs) | 3 |
| Identity conflicts flagged (one MRN, two people) | 2 |
| Records quarantined | 3 |

How it works, in short (rules in [docs/05-ALGORITHMS.md](docs/05-ALGORITHMS.md) section 1):

- **Cleaning.** Dates in any of the source formats become ISO 8601. Ambiguous `NN/NN/YYYY` dates are read as US month/day with a warning, and impossible dates such as `02/30/2024` are rejected. Gender codes map to FHIR AdministrativeGender, MRNs become 8 digits, names are parsed and title-cased, and lab flags are recomputed from the reference range and a critical value table.
- **Identity.** Records on one MRN are confirmed by DOB and name similarity. Different MRNs merge only on an exact match of family name, first given name and DOB. When two people share an MRN they stay separate, and both are flagged for review.
- **Duplicates.** Identical text is an exact duplicate. Text that differs only in case or spacing, with a compatible type and dates within a day, is a near duplicate. The richest copy is kept, and duplicates are never matched across patients.
- **Audit.** Every changed field gets an audit entry with its rule id, the value before and after, and a severity. A record that needed no change gets none. Unusable records go to quarantine with a reason (`identity_unresolvable`, `empty_document`, `read_error`, `path_outside_raw_dir`).
- **Safety.** Readers never leave `DATA_RAW_DIR`, including through symlinks. Logs carry counts and ids only, and an ingest that finds no patients leaves the database untouched.

A test checks every number above, and every injected issue location, against `data/raw/_ground_truth.json`.

## FHIR normalization (Task 2)

`make normalize` (`ehr-mip normalize`) turns each patient's clean records into one FHIR R4 `collection` Bundle, validates it and stores it in SQLite with an index row per resource. It also writes `reports/validation_report.json` and `reports/validation_report.md`.

| Measure | Seed 42 |
|---|---|
| Bundles (valid) | 60 (60) |
| Errors / warnings / info | 0 / 4 / 2 |
| Patient, Encounter | 60, 97 |
| DocumentReference (notes) | 90 |
| DiagnosticReport (imaging and pathology, labs) | 60, 95 |
| Observation | 291 |

The 4 warnings are the flagged identity conflicts (two people on each of two MRNs); the 2 infos are scanned reports without an encounter.

- **Mapping** ([docs/03-DATA-MODEL.md](docs/03-DATA-MODEL.md) section 5). Notes become DocumentReferences with the text attached. Imaging and pathology reports become DiagnosticReports with the impression as `conclusion`. Each lab report becomes a DiagnosticReport whose results are Observations with UCUM units, reference ranges and interpretation codes. Merged MRNs appear as `use=old` identifiers, and identity conflicts carry a tag.
- **Validation.** Every bundle is checked with `fhir.resources` (R4B package, see [ADR-001](docs/decisions/ADR-001-fhir-resources-r4b.md)) plus business rules: references resolve inside the bundle, every clinical resource points to the patient, required codes are valid, and dates are plausible. The library checks code format but not value sets, so the validator adds the value-set check itself.
- **Stability.** Resource ids are deterministic UUIDv5 keys and `bundle_hash` ignores timestamps, so an unchanged patient keeps the same hash on every run. Later phases use that hash as the summary cache key.
- **No invented data.** A document with only a date never gets a made-up time, and a lab report is given a panel code only when it holds exactly that panel's tests.

## Clinical summaries (Task 3)

`make summarize` (`ehr-mip summarize`) writes one structured summary per patient: chief concern, up to 5 key diagnoses, the 5 most recent media records, flagged anomalies and a short overview, at most 200 words, each item linked to the records it came from, always with the "AI-generated, not a substitute for clinical judgment" disclaimer.

- **Providers.** With `ANTHROPIC_API_KEY` set, Claude (`claude-haiku-5-5`, structured output, effort `low`) writes the summary. Without a key, or when Claude fails, refuses or the daily token budget is spent, an offline extractive provider builds it from the record text only ([ADR-006](docs/decisions/ADR-006-extractive-fallback.md)). The system runs fully without a key.
- **Privacy.** The model sees age, sex and de-identified clinical text. Names, MRNs, dates of birth, phone numbers, addresses and emails are removed from free text, and instruction-like text is removed before the prompt is built.
- **Guardrails** ([docs/05](docs/05-ALGORITHMS.md) section 3.5). Items citing records that are not in the patient's bundle are dropped, a diagnosis must be written in the records it cites or it becomes `suspected`, every high-severity rule anomaly is restored if missing, and a long answer gets one shorten retry and then a deterministic trim. Confidence is computed, not taken from the model.
- **Prompts** are versioned files under `backend/src/ehr_mip/summarization/prompts/`, with a snapshot test of the rendered prompt. A released version is never edited.
- **Caching and cost.** Summaries are cached by patient, `bundle_hash`, prompt version and model, so a second run makes zero model calls. Every call is logged to `llm_calls` with tokens, latency and an estimated cost, and `LLM_DAILY_TOKEN_BUDGET` caps daily spend.

`make eval` (`ehr-mip eval`) scores the 60 synthetic patients plus 5 golden and 5 adversarial cases and writes `reports/eval_report.{json,md}`. Offline results (extractive, seed 42):

| Gate | Result | Target |
|---|---|---|
| Schema, disclaimer, length ≤ 200 words | 100% | 100% |
| Final grounding | 100% | 100% |
| Diagnosis support | 100% | ≥ 95% |
| High anomaly recall | 100% | 100% |
| Golden cases (required facts, no forbidden claims) | 5 / 5 | all |
| Adversarial cases (injection, sparse, conflict, long note, labs only) | 5 / 5 | all |
| Ground truth diagnosis recall | 87.5% | ≥ 85% |

The recall misses are hyponatremia and hyperlipidemia that appear only as lab values, never written in a note; the summarizer does not infer diagnoses. The manual review sheet (`docs/eval/manual_review_<model>.md`) is created for a person to score and is never overwritten.

## Search and API (Task 4)

`make index` (`ehr-mip index`) chunks every note and diagnostic report plus each patient's summary into windows of about 180 words, embeds them with `all-MiniLM-L6-v2` and stores them in an in-process Chroma collection (cosine). Names, MRNs and contact details are scrubbed before embedding. The first run downloads the model (about 90 MB) into `data/generated/hf-cache`; later runs load it from there without a network call. On the synthetic data: 305 chunks from 245 records and 60 summaries.

`make api` serves the endpoints in [docs/04-API-CONTRACT.md](docs/04-API-CONTRACT.md): `/health`, `/ready`, `POST /search`, `/patients/{key}`, `/patients/{key}/resources`, `/patients/{key}/summary` and `/resources/{type}/{id}`, plus `/metrics`.

```bash
curl -s -X POST 'http://localhost:8000/search?resource_type=DiagnosticReport&date_from=2024-06-01' \
  -H 'Content-Type: application/json' \
  -d '{"query": "worsening kidney function with high potassium"}'
```

- **Ranking** ([docs/05](docs/05-ALGORITHMS.md) section 4). Semantic by default; `mode=hybrid` fuses BM25 and vector ranks with reciprocal rank fusion. A query shaped like an MRN returns that patient's newest records. Results are one per resource, sorted by score, with a snippet, highlight ranges and the patient's chief concern.
- **Filters.** Repeatable `resource_type`, inclusive `date_from` and `date_to` (undated records are excluded once a date is set), `top_k` up to 20, `patient_key`.
- **Caching.** Search results are cached for 60 s under the index version, so a reindex invalidates them; responses carry `X-Cache`. The cache holds ids, scores and scrubbed snippets only; patient details are joined afterwards. Patient responses are cached in process for 5 minutes and never in a shared backend.
- **Reindexing while serving** builds the new collection next to the live one and swaps it in, so searches keep working during `make index`.
- **Security** ([docs/09](docs/09-SECURITY.md) section 5). Security headers and `no-store` on every response, per-IP rate limits with `RateLimit-*` headers and 429 problems, a 16 KB body limit, strict validation (422 with field errors), RFC 9457 problem responses without stack traces, and a log processor that removes PHI.
- **Latency** (NFR-01) with the real model, 20 uncached queries: p50 18 ms, p95 35 ms; limit 2 s, target 300 ms (`tests/perf/test_search_latency.py`).

`make openapi` exports `docs/openapi.json`; a snapshot test fails on any undocumented API change.

## Clinician UI (Task 5)

`make dev` runs the API and the web app; open http://localhost:5173. The design system is in [docs/06-UI-DESIGN.md](docs/06-UI-DESIGN.md).

- **Search** as you type (300 ms debounce, two characters minimum). Previous results stay on screen while the next search runs. Each card shows the patient name and MRN, age and sex, record type, date and title, the matched passage with highlighted terms, the AI chief concern and the relevance score, with a "Why this result" explanation.
- **Filters** for record type and date range (presets or a range calendar that cannot produce an end before its start). Query, filters and the open patient live in the URL, so links and the back button work.
- **Patient drawer** with the AI summary and the linked FHIR records. The summary always starts with the disclaimer, labels every AI element, shows provenance (model or "Offline summary", prompt version, cache), marks suspected diagnoses and data quality anomalies, and shows confidence with its rationale. Evidence links jump to the cited record; each record opens with readable sections and its FHIR JSON.
- **States**: loading skeletons, idle with example searches, no results, errors with the request id, and a "run `make pipeline`" notice when nothing is indexed.
- **Keyboard**: `/` or Ctrl/Cmd+K to search, ↓ into results, ↑ ↓ Home End between results, Enter to open, `[` `]` to switch tabs, Esc to close. Focus returns to the result you opened.
- **Responsive and themed**: 390, 1024 and 1440 px layouts, filters in a bottom sheet and a full-screen drawer on phones, light and dark themes.

Every JSON example in [docs/04-API-CONTRACT.md](docs/04-API-CONTRACT.md) is extracted into fixtures (`pnpm contract:fixtures`) and must parse with the Zod schemas; component tests and Storybook use the same fixtures. `make e2e` runs Playwright against the real API (keyboard-only and mobile paths, axe with color contrast in both themes); `make storybook` opens the component workshop.

## Project structure

```
backend/    Python package ehr_mip (uv): ingestion, fhir, summarization, search, api layers
frontend/   React 19, Vite, Tailwind v4, shadcn/ui (Base UI), TanStack Router and Query
scripts/    synthetic data generator
data/raw/   committed synthetic input; data/generated/ holds local state (gitignored)
docs/       specification, architecture, contracts, design system, ADRs
```

Backend layers only import downward (`api > search > summarization > fhir > ingestion > db`), enforced by import-linter.

## Quality gates

| Command | What it runs |
|---|---|
| `make check` | ruff, import-linter, mypy `--strict`, pytest with an 85 percent coverage gate, ESLint (type-checked, jsx-a11y), Prettier, tsc, Vitest with axe and the contract fixture test |
| `make e2e` | Playwright end-to-end tests against the real API, with axe including color contrast |
| `make security` | pip-audit, pnpm audit, gitleaks, and Trivy once images exist |

Pre-commit runs the same linters plus gitleaks and private key detection; commit messages follow Conventional Commits. Accepted dependency findings and their reasons are listed in [docs/09-SECURITY.md](docs/09-SECURITY.md) section 8.1.

## Documentation

The specification lives in [docs/](docs/): requirements in [01-SPEC.md](docs/01-SPEC.md), architecture in [02-ARCHITECTURE.md](docs/02-ARCHITECTURE.md), the API contract in [04-API-CONTRACT.md](docs/04-API-CONTRACT.md) and the design system in [06-UI-DESIGN.md](docs/06-UI-DESIGN.md). Architecture decisions are in [docs/decisions/](docs/decisions/).

## Data and privacy

The repository contains synthetic data only. Logs carry ids, never names, MRNs, dates of birth or note text, and the language model only ever sees de-identified context (age, sex and clinical text).
