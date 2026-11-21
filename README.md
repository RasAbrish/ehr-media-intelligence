# EHR Media Intelligence Platform

An AI pipeline that ingests raw EHR exports, cleans and normalizes them to HL7 FHIR R4, writes grounded clinical summaries with Claude and gives clinicians a fast semantic search interface. Built for the Onye AI full-stack assessment. All data is synthetic.

> Status: Phase 2 (FHIR normalization). Summaries, search and the UI arrive in later phases; see [docs/08-DELIVERY.md](docs/08-DELIVERY.md).

## Quick start

Requirements: Python 3.12, [uv](https://docs.astral.sh/uv/), Node 20.11 or newer, pnpm, git. Docker is needed from Phase 6.

```bash
make setup     # backend (uv) and frontend (pnpm) dependencies, git hooks
make data      # regenerate the seeded synthetic data in data/raw/
make check     # lint, type check and tests for backend and frontend
make ingest    # read, clean, resolve identities and dedupe into SQLite
make normalize # one validated FHIR R4 bundle per patient, plus the validation report
make web       # web app on http://localhost:5173
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
| `make check` | ruff, import-linter, mypy `--strict`, pytest with an 85 percent coverage gate, ESLint (type-checked, jsx-a11y), Prettier, tsc, Vitest with axe |
| `make security` | pip-audit, pnpm audit, gitleaks, and Trivy once images exist |

Pre-commit runs the same linters plus gitleaks and private key detection; commit messages follow Conventional Commits. Accepted dependency findings and their reasons are listed in [docs/09-SECURITY.md](docs/09-SECURITY.md) section 8.1.

## Documentation

The specification lives in [docs/](docs/): requirements in [01-SPEC.md](docs/01-SPEC.md), architecture in [02-ARCHITECTURE.md](docs/02-ARCHITECTURE.md), the API contract in [04-API-CONTRACT.md](docs/04-API-CONTRACT.md) and the design system in [06-UI-DESIGN.md](docs/06-UI-DESIGN.md). Architecture decisions are in [docs/decisions/](docs/decisions/).

## Data and privacy

The repository contains synthetic data only. Logs carry ids, never names, MRNs, dates of birth or note text, and the language model only ever sees de-identified context (age, sex and clinical text).
