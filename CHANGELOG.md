# Changelog

All notable changes to this project are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses one entry per delivery phase.

## [Unreleased]

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
