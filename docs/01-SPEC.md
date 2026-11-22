# 01. Product Specification

Source brief: *NYCEDC / Onye 2026 AI Full-stack Assessment: EHR Media Intelligence Platform*.

## 1. Problem and goal

Clinical staff using Epic EHR lose time manually reviewing unstructured patient media (lab PDFs, imaging notes, discharge summaries, scanned documents) that sit outside structured fields.

**Goal:** an AI pipeline that ingests raw EHR data, cleans and normalizes it to HL7 FHIR R4, generates clinical summaries, and gives clinicians a search interface that finds relevant records in seconds.

## 2. Users

| Persona | Need | Success looks like |
|---|---|---|
| Clinician (physician, NP) | Find a specific finding across a patient's history fast | Types a phrase, gets the right record in the top 5, opens the patient, reads a trustworthy summary in under 30 seconds |
| Nurse / care coordinator | Spot abnormal results and gaps | Anomalies flagged with severity and a link to the source |
| Data / informatics reviewer (the assessor) | Trust the data pipeline | Sees what was cleaned, merged, flagged and why, plus FHIR validation results |

## 3. User stories

| ID | Story |
|---|---|
| US-01 | As a clinician, I type a natural language query and see ranked records update as I type. |
| US-02 | As a clinician, I narrow results by resource type and date range. |
| US-03 | As a clinician, each result shows the patient name, MRN, record date, record type, relevance and a one-line AI summary. |
| US-04 | As a clinician, I open a patient and read the full AI summary with chief concern, diagnoses, recent media and anomalies. |
| US-05 | As a clinician, I can see every FHIR resource linked to the patient and open the source text. |
| US-06 | As a clinician, I can tell AI-generated content from source data at a glance and see a disclaimer. |
| US-07 | As a keyboard or screen reader user, I can do all of the above without a mouse. |
| US-08 | As a reviewer, I can see ingestion statistics, the audit log and FHIR validation issues. |
| US-09 | As a reviewer, I can run the whole system without an API key. |

## 4. Functional requirements

### Task 1: Ingestion and cleaning
| ID | Requirement | Tier |
|---|---|---|
| FR-1.1 | Ingest JSON (simulated EHR export) | R |
| FR-1.2 | Ingest CSV (lab results) and plain text (scanned notes) | R |
| FR-1.3 | Handle missing fields without crashing; record them in the audit log | R |
| FR-1.4 | Normalize inconsistent date formats to ISO 8601 | R |
| FR-1.5 | Remove exact and near duplicate records | R |
| FR-1.6 | Resolve conflicting patient identifiers (merge same person, flag conflicts) | R |
| FR-1.7 | Normalize DOB, gender codes (FHIR AdministrativeGender) and MRN format | R |
| FR-1.8 | Output validated Pydantic models (intermediate representation) | R |
| FR-1.9 | Per-record audit log of every change | R |
| FR-1.10 | Quarantine unusable records with a reason | R |
| FR-1.11 | Unit tests for at least 3 cleaning edge cases (target 25+) | R |

### Task 2: FHIR R4 normalization
| ID | Requirement | Tier |
|---|---|---|
| FR-2.1 | Map Patient, DocumentReference, DiagnosticReport | R |
| FR-2.2 | Map Encounter and Observation | P1 (Encounter needed for references, built in R) |
| FR-2.3 | Validate with `fhir.resources` | R |
| FR-2.4 | One Bundle per patient with correct `subject` and `encounter` references | R |
| FR-2.5 | Validate every Bundle; produce a clear validation report (JSON + Markdown + API) | R |
| FR-2.6 | Store Bundles in SQLite for retrieval | R |
| FR-2.7 | Deterministic resource ids (idempotent re-runs) | R |
| FR-2.8 | Optional strict R4 check with the official HL7 validator | P2 |

### Task 3: AI summarization
| ID | Requirement | Tier |
|---|---|---|
| FR-3.1 | Summarize each patient's document history with the Claude API | R |
| FR-3.2 | Summary contains chief concern, key diagnoses, recent media (imaging, labs), flagged anomalies | R |
| FR-3.3 | Under 200 words, clinically accurate (grounded in records) | R |
| FR-3.4 | Cache keyed by patient id + record hash; no repeat API calls on re-run | R |
| FR-3.5 | Confidence field and AI disclaimer on every summary | R |
| FR-3.6 | Evidence references from each claim to source resources | P1 |
| FR-3.7 | Offline extractive fallback when no API key | P1 |
| FR-3.8 | Evaluation harness with metrics report | P1 |
| FR-3.9 | Regenerate summary on demand (cache bypass) | P2 |

### Task 4: Semantic search
| ID | Requirement | Tier |
|---|---|---|
| FR-4.1 | Embed FHIR document text and AI summaries with all-MiniLM-L6-v2 | R |
| FR-4.2 | Store vectors in ChromaDB | R |
| FR-4.3 | `POST /search` takes free text, returns top 5 matches with relevance scores | R |
| FR-4.4 | Filter by resource type and date range via query parameters | R |
| FR-4.5 | Hybrid lexical + semantic ranking and MRN lookup | P1 |
| FR-4.6 | Matched snippet per result | P1 |

### Task 5: Frontend
| ID | Requirement | Tier |
|---|---|---|
| FR-5.1 | Search bar calling `POST /search` with real-time results | R |
| FR-5.2 | Result cards: name/MRN, record date, resource type badge, relevance score, AI summary snippet | R |
| FR-5.3 | Patient drawer: full AI summary and linked FHIR resources | R |
| FR-5.4 | Filters: resource type dropdown, date range picker | R |
| FR-5.5 | Responsive layout, loading states, empty states | R |
| FR-5.6 | ARIA labels, keyboard navigation for search and results | R |
| FR-5.7 | Patient directory (TanStack Table) | P1 |
| FR-5.8 | Data quality dashboard | P1 |
| FR-5.9 | URL-synced state, keyboard shortcuts, dark mode | P1 |
| FR-5.10 | Timeline, FHIR JSON viewer, bundle download | P2 |

### Cross-cutting: Security (detail in `09-SECURITY.md`)
| ID | Requirement | Tier |
|---|---|---|
| FR-6.1 | Security headers on API and web responses | R |
| FR-6.2 | Rate limits with `RateLimit-*` headers and 429 problem responses | R |
| FR-6.3 | Input limits (body size, query length, page size, top_k, UUID path ids) | R |
| FR-6.4 | PHI-free logs (redaction processor) and masked audit values in API | R |
| FR-6.5 | Prompt injection defense with a planted adversarial note test | R |
| FR-6.6 | Supply chain scanning (pip-audit, pnpm audit, gitleaks, Trivy, CodeQL, Dependabot) | P1 |
| FR-6.7 | Hardened containers (non-root, read-only, dropped capabilities) | P1 |
| FR-6.8 | Admin endpoints off by default, token protected when on | P2 |
| FR-6.9 | Sign-in with email and password, server-side sessions, every data route behind a session; accounts created by command; a published demo login for the synthetic demo | P1 |

### Cross-cutting: AI governance (detail in `10-AI-DESIGN.md`)
| ID | Requirement | Tier |
|---|---|---|
| FR-7.1 | Versioned prompt files with rendered prompt snapshot test | R |
| FR-7.2 | AI system card in repo | P1 |
| FR-7.3 | Golden and adversarial eval sets with CI gates (no API key needed) | P1 |
| FR-7.4 | LLM call telemetry (`llm_calls` table, tokens, cost, latency, status) | P1 |
| FR-7.5 | Summary feedback (helpful / not helpful + reason) stored per prompt version | P1 |
| FR-7.6 | Daily token budget guard | P2 |

### Cross-cutting: UX quality (detail in `06-UI-DESIGN.md` sections 12 to 17)
| ID | Requirement | Tier |
|---|---|---|
| FR-8.1 | Content and microcopy guidelines applied (sentence case, units, date format, error formula) | R |
| FR-8.2 | AI UX patterns: label, disclaimer, citations, confidence rationale, provenance, feedback | R (label, disclaimer, confidence) / P1 (rest) |
| FR-8.3 | Performance budget: LCP < 2.0 s, INP < 200 ms, CLS < 0.1, initial JS < 250 KB gzip | P1 |
| FR-8.4 | Storybook for shared components with a11y addon | P1 |
| FR-8.5 | Visual regression screenshots (Playwright) for key screens in light and dark | P2 |
| FR-8.6 | First-run onboarding hints and "why this result" explanation | P1 |
| FR-8.7 | Usability test script with 5 tasks and recorded results in `docs/ux/usability-test.md` | P2 |

### Cross-cutting: Platform and developer experience (detail in `07-ENGINEERING-PRACTICES.md`)
| ID | Requirement | Tier |
|---|---|---|
| FR-9.1 | Layered caching: SQLite summary cache (system of record), in-process TTL cache for search, optional Redis backend | R (SQLite) / P1 (TTL) / P2 (Redis) |
| FR-9.2 | `/metrics` Prometheus endpoint | P1 |
| FR-9.3 | Readiness, liveness, graceful shutdown | R |
| FR-9.4 | Repo hygiene: PR template, CODEOWNERS, commitlint, EditorConfig, CHANGELOG | P1 |

## 5. Non-functional requirements

| ID | Requirement | Measure |
|---|---|---|
| NFR-01 | Search latency | Under 2 s for 50 records (hard). Target p95 under 300 ms locally on the ~250 record synthetic set |
| NFR-02 | Privacy | Synthetic data only; no PHI in logs; de-identified LLM context |
| NFR-03 | Reproducibility | Seeded data generator; deterministic ids; idempotent pipeline |
| NFR-04 | Accessibility | WCAG 2.2 AA; zero serious or critical axe violations |
| NFR-05 | Code quality | ruff, mypy strict, ESLint, TS strict; backend coverage ≥ 85 percent |
| NFR-06 | Portability | `docker compose up` runs everything; local dev with uv and pnpm |
| NFR-07 | Resilience | LLM failures fall back per patient; pipeline never aborts on a bad record |
| NFR-08 | Observability | JSON logs with request id; `Server-Timing` and `took_ms` on search |
| NFR-09 | Cost | Cache prevents repeat LLM calls; small model tier by default; cost per run reported |
| NFR-10 | Security | Zero high or critical findings from `make security`, apart from the exceptions listed in `09-SECURITY.md` section 8.1; all `09-SECURITY.md` section 11 tests pass |
| NFR-11 | Frontend performance | Lighthouse performance, accessibility, best practices ≥ 90 at 4x CPU slowdown without network throttling (`06-UI-DESIGN.md` section 15); Core Web Vitals within FR-8.3 |
| NFR-12 | AI quality | All gates in `10-AI-DESIGN.md` section 6.2 pass |
| NFR-13 | Availability of AI feature | Summaries available without API key (extractive) and labeled as such |

## 6. Scope tiers

| Tier | Rule |
|---|---|
| R (Required) | Everything the brief asks. Must ship and be tested |
| P1 (High-value extras) | Build only after all R items pass |
| P2 (Nice to have) | Only if time remains after P1 core |

**Out of scope:** real EHR integration, single sign-on, roles, password reset by email, real OCR of image PDFs, Practitioner/Organization resources, clinical decision support, multi-tenant deployment.

**Assumptions:** US-origin data (MM/DD default for ambiguous dates), English text, a few named users with equal access, CPU-only machine.

## 7. Acceptance criteria and traceability

| Req | Acceptance check | Verified by |
|---|---|---|
| FR-1.1/1.2 | `ehr-mip ingest` reads all 3 formats and prints stats | `tests/integration/test_pipeline_e2e.py` |
| FR-1.3 to 1.7 | Stats match `data/raw/_ground_truth.json` (duplicates, merges, conflicts) | `test_ingestion_matches_ground_truth` |
| FR-1.8/1.9 | Every changed field has an AuditEntry; untouched records have none | `test_untouched_record_has_no_audit` + rule tests |
| FR-1.11 | 25+ unit tests in `tests/unit/ingestion` | CI |
| FR-2.1/2.3 | Every mapper output passes `model_validate` | mapper tests |
| FR-2.4 | All references resolve inside the bundle | `test_reference_integrity` |
| FR-2.5 | Invalid fixture produces readable issues; report files exist | `test_validation_report_captures_errors` |
| FR-2.6/2.7 | Store round-trip; identical `bundle_hash` on re-run | store tests |
| FR-3.1/3.2/3.5 | Every summary has all parts, confidence, disclaimer | schema tests, eval report |
| FR-3.3 | `word_count ≤ 200` for 100 percent; grounding 100 percent after guardrails | guardrail tests, eval |
| FR-3.4 | Second run: 0 provider calls, 100 percent cache hits | `test_cache_prevents_repeat_calls` |
| FR-4.1/4.2 | `ehr-mip index` reports chunks and resources | index test |
| FR-4.3 | ≤ 5 results, sorted by score desc (by date with `sort=newest`), contract-conformant | API tests + contract snapshot |
| FR-4.4 | Type filter and inclusive date range work; bad range → 422 | filter tests |
| NFR-01 | Max latency under 2 s across 20 queries | `tests/perf/test_search_latency.py` |
| FR-5.1 | Results appear while typing; stale results kept during refetch | component + e2e |
| FR-5.2 | All five card fields rendered | `ResultCard.test.tsx` |
| FR-5.3 | Drawer shows summary sections and resource table | `PatientDrawer.test.tsx`, e2e |
| FR-5.4 | Filters update URL and results; invalid range blocked | component tests |
| FR-5.5 | Loading, empty, error states visible and announced | component tests, e2e mobile |
| FR-5.6 / NFR-04 | Keyboard path works; axe clean | keyboard tests, axe tests |
| FR-6.x / NFR-10 | Headers, limits, redaction, injection tests pass; scanners clean | `09-SECURITY.md` §11 tests, CI security job |
| FR-7.x / NFR-12 | Prompt snapshot, golden and adversarial gates, telemetry rows written, feedback stored | `10-AI-DESIGN.md` §6 gates, API tests |
| FR-8.x / NFR-11 | Microcopy review, Storybook builds, Lighthouse CI ≥ 90 | Lighthouse CI, Storybook build in CI |
| FR-9.x | Cache hit tests (TTL and Redis), `/metrics` exposes counters, shutdown closes resources | `test_search_cache_*`, `test_metrics_endpoint` |
| Deliverables | Commits per coherent change with one marked per major task, README, pyproject + requirements.txt, pytest runnable, no real data, write-up PDF | `08-DELIVERY.md` checklist |
