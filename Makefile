# EHR Media Intelligence Platform. Run `make` or `make help` for the target list.
# Targets for later phases exist already and say which phase delivers them.

SHELL := /bin/bash
.DEFAULT_GOAL := help
.SHELLFLAGS := -eu -o pipefail -c

UV  ?= uv
PNPM ?= pnpm
BACKEND := backend
FRONTEND := frontend
SYNTH_SEED ?= 42
SYNTH_PATIENTS ?= 60

RUN := cd $(BACKEND) && $(UV) run

# Accepted pip-audit findings. Each one is justified in docs/09-SECURITY.md section 8.1.
# All five affect the ChromaDB *server* HTTP API, which this project never runs (in-process
# PersistentClient only). Re-check whenever chromadb is upgraded.
PIP_AUDIT_IGNORE := PYSEC-2026-311 PYSEC-2026-3813 PYSEC-2026-3814 PYSEC-2026-3815
CLI := $(RUN) ehr-mip

define pending
	@echo "make $@: available from Phase $(1) (docs/08-DELIVERY.md)." >&2; exit 2
endef

.PHONY: help setup data ingest normalize summarize index pipeline api web dev test test-backend \
	test-frontend e2e lint fmt typecheck check security eval openapi storybook lighthouse \
	validate-official docker-up docker-up-redis writeup-pdf requirements clean \
	audit-python audit-js secrets trivy sbom

help: ## List targets
	@awk 'BEGIN {FS = ":.*## "; printf "Usage: make <target>\n\n"} \
		/^[a-zA-Z_-]+:.*## / {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

# ---------------------------------------------------------------- setup and data

setup: ## Install backend (uv) and frontend (pnpm) deps and git hooks
	cd $(BACKEND) && $(UV) sync --extra dev --extra redis
	cd $(FRONTEND) && $(PNPM) install --frozen-lockfile
	if [ -d .git ]; then \
		$(UV) run --project $(BACKEND) pre-commit install --install-hooks \
			--hook-type pre-commit --hook-type commit-msg; \
	fi

data: ## Generate seeded synthetic raw data in data/raw/
	$(RUN) python ../scripts/generate_synthetic_data.py \
		--seed $(SYNTH_SEED) --patients $(SYNTH_PATIENTS) --out ../data/raw

requirements: ## Export backend/requirements.txt from uv.lock
	cd $(BACKEND) && $(UV) export --no-hashes --no-dev --extra redis --no-emit-project -q \
		> requirements.txt

# ---------------------------------------------------------------- pipeline

ingest: ## Read, clean, resolve identities, dedupe (Phase 1)
	$(CLI) ingest

normalize: ## Map to FHIR R4B bundles and validate (Phase 2)
	$(CLI) normalize

summarize: ## Generate clinical summaries (Phase 3)
	$(CLI) summarize

index: ## Chunk, embed and index (Phase 4)
	$(CLI) index

pipeline: ## ingest, normalize, summarize, index (idempotent)
	$(CLI) run-all

eval: ## Summary quality report into reports/ (Phase 3)
	$(CLI) eval

# ---------------------------------------------------------------- run

api: ## Run the API on :8000 (Phase 4)
	$(CLI) serve

web: ## Run the web app on :5173
	cd $(FRONTEND) && $(PNPM) dev

dev: ## Run API and web together
	trap 'kill 0' EXIT; \
	$(MAKE) --no-print-directory api & \
	$(MAKE) --no-print-directory web & \
	wait

# ---------------------------------------------------------------- quality gates

lint: ## ruff, import-linter, ESLint and Prettier check
	$(RUN) ruff check src tests ../scripts
	$(RUN) ruff format --check src tests ../scripts
	$(RUN) lint-imports
	cd $(FRONTEND) && $(PNPM) -s lint && $(PNPM) -s format:check

fmt: ## Format Python and TypeScript
	$(RUN) ruff check --fix src tests ../scripts
	$(RUN) ruff format src tests ../scripts
	cd $(FRONTEND) && $(PNPM) -s format

typecheck: ## mypy --strict and tsc
	$(RUN) mypy src ../scripts/generate_synthetic_data.py ../scripts/export_openapi.py
	cd $(FRONTEND) && $(PNPM) -s typecheck

test-backend: ## pytest with coverage gate (85 percent)
	$(RUN) pytest

test-frontend: ## Vitest
	cd $(FRONTEND) && $(PNPM) -s test

test: test-backend test-frontend ## All unit and integration tests

check: lint typecheck test ## lint + typecheck + test (gate before every commit)
	@echo "make check: all green"

security: audit-python audit-js secrets trivy ## pip-audit, pnpm audit, gitleaks, Trivy

audit-python: ## pip-audit on backend/requirements.txt (accepted findings: PIP_AUDIT_IGNORE)
	cd $(BACKEND) && $(UV) tool run pip-audit --progress-spinner off \
		--requirement requirements.txt --disable-pip --no-deps \
		$(foreach id,$(PIP_AUDIT_IGNORE),--ignore-vuln $(id))

audit-js: ## pnpm audit, failing on high or critical
	cd $(FRONTEND) && $(PNPM) audit --audit-level=high

secrets: ## gitleaks over staged changes and the full git history
	$(UV) tool run pre-commit run gitleaks --all-files
	if git rev-parse --verify -q HEAD >/dev/null; then \
		$(UV) tool run pre-commit run --hook-stage manual gitleaks-history --all-files; \
	else \
		echo "gitleaks history: skipped (no commits yet)"; \
	fi

trivy: ## Trivy scan of both built images (HIGH, CRITICAL; accepted: .trivyignore.yaml)
	if command -v docker >/dev/null && docker image inspect ehr-mip-api:local >/dev/null 2>&1; then \
		bash scripts/image_scan.sh scan; \
	else \
		echo "trivy: skipped (no images built; run docker compose build)"; \
	fi

sbom: ## CycloneDX SBOM of both built images into reports/
	bash scripts/image_scan.sh sbom

# ---------------------------------------------------------------- later phases

e2e: ## Playwright end-to-end tests (needs `make pipeline`; own servers on a copy of the data)
	cd $(FRONTEND) && $(PNPM) e2e

openapi: ## Export docs/openapi.json and run the contract snapshot (Phase 4)
	$(RUN) python ../scripts/export_openapi.py
	$(RUN) pytest tests/contract --no-cov -q

storybook: ## Component workshop with the a11y addon on :6006
	cd $(FRONTEND) && $(PNPM) storybook

lighthouse: ## Bundle budget and Lighthouse CI against the built app (needs `make pipeline`)
	bash scripts/lighthouse.sh

validate-official: ## Optional HL7 validator run (P2)
	$(call pending,6)

docker-up: ## Build and start the stack on http://localhost:8080
	docker compose up --build --detach --wait --wait-timeout 900

docker-up-redis: ## The same with Redis for cache and rate limits
	docker compose --profile redis up --build --detach --wait --wait-timeout 900

writeup-pdf: ## Render docs/WRITEUP.md to PDF (Phase 7)
	$(call pending,7)

clean: ## Remove generated state and build output (keeps data/raw)
	rm -rf data/generated $(FRONTEND)/dist $(FRONTEND)/coverage $(BACKEND)/.coverage \
		$(BACKEND)/htmlcov $(BACKEND)/.pytest_cache $(BACKEND)/.mypy_cache $(BACKEND)/.ruff_cache
