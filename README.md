# EHR Media Intelligence Platform

An AI pipeline that ingests raw EHR exports, cleans and normalizes them to HL7 FHIR R4, writes grounded clinical summaries with Claude and gives clinicians a fast semantic search interface. Built for the Onye AI full-stack assessment. All data is synthetic.

> Status: Phase 0 (scaffold, tooling and synthetic data). Pipeline stages, API and search arrive in later phases; see [docs/08-DELIVERY.md](docs/08-DELIVERY.md).

## Quick start

Requirements: Python 3.12, [uv](https://docs.astral.sh/uv/), Node 20.11 or newer, pnpm, git. Docker is needed from Phase 6.

```bash
make setup     # backend (uv) and frontend (pnpm) dependencies, git hooks
make data      # regenerate the seeded synthetic data in data/raw/
make check     # lint, type check and tests for backend and frontend
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
