# 02. Architecture

All diagrams are Mermaid and render on GitHub. Keep them in sync with the code; update the diagram in the same PR as the change.

## 1. System context (C4 level 1)

```mermaid
flowchart LR
    clin(["Clinician<br/>(browser)"])
    rev(["Reviewer / data engineer<br/>(CLI + browser)"])
    sys["EHR Media Intelligence Platform<br/>ingest, normalize, summarize, search"]
    raw[("Raw EHR exports<br/>JSON, CSV, TXT<br/>(synthetic)")]
    claude["Anthropic Claude API<br/>(external)"]
    hf["Hugging Face Hub<br/>(model download, first run only)"]

    clin -- "search, read summaries" --> sys
    rev -- "run pipeline, inspect quality" --> sys
    raw -- "files on disk" --> sys
    sys -- "de-identified context<br/>HTTPS" --> claude
    sys -- "download all-MiniLM-L6-v2" --> hf
```

## 2. Containers (C4 level 2)

```mermaid
flowchart TB
    subgraph browser["Browser"]
        spa["Web App<br/>React 19, Vite, Tailwind v4, shadcn/ui<br/>TanStack Query, Table, Router, Zod"]
    end

    subgraph host["Host / docker compose"]
        nginx["web container<br/>nginx: static dist + /api proxy"]
        api["api container<br/>FastAPI + Uvicorn<br/>Python 3.12"]
        cli["Pipeline CLI<br/>ehr-mip (Typer)<br/>same image as api"]
        sqlite[("SQLite<br/>ehr_mip.db<br/>clean data, FHIR bundles,<br/>audit, validation, summary cache")]
        chroma[("ChromaDB<br/>PersistentClient<br/>collection ehr_records")]
        model[["all-MiniLM-L6-v2<br/>in-process, CPU"]]
        rawfiles[("data/raw<br/>JSON, CSV, TXT")]
        redis[("Redis 7 (optional profile)<br/>search response cache,<br/>rate limit counters")]
    end

    claude["Claude API"]

    spa -- "HTTP JSON /api/*" --> nginx
    nginx -- "proxy, strip /api" --> api
    api --> sqlite
    api --> chroma
    api --> model
    api -. "regenerate summary" .-> claude
    api -. "CACHE_BACKEND=redis" .-> redis
    cli --> rawfiles
    cli --> sqlite
    cli --> chroma
    cli --> model
    cli -- "summarize" --> claude
```

In local dev, Vite's dev server replaces nginx and proxies `/api` to `localhost:8000`.

## 3. Backend components (C4 level 3)

```mermaid
flowchart TB
    subgraph api_layer["api"]
        routers["routers<br/>search, patients, resources,<br/>quality, system, pipeline"]
        deps["deps.py<br/>DI: settings, repos, services"]
        mw["middleware<br/>request id, timing, CORS"]
        errs["errors.py<br/>RFC 9457 problem+json"]
    end

    subgraph search_layer["search"]
        ssvc["SearchService"]
        emb["Embedder"]
        vstore["VectorStore (Chroma)"]
        lex["LexicalIndex (BM25)"]
        rank["ranking.py (RRF, dedupe)"]
        filt["filters.py (where builder)"]
        chunk["Chunker"]
    end

    subgraph sum_layer["summarization"]
        sumsvc["SummaryService"]
        ctx["ContextBuilder (de-identify)"]
        anom["AnomalyDetector (rules)"]
        prov["Providers: Anthropic,<br/>Extractive, Fake"]
        guard["Guardrails"]
        cache["SummaryCache"]
        evalh["Evaluator"]
    end

    subgraph fhir_layer["fhir"]
        mappers["Mappers: Patient, Encounter,<br/>DocumentReference,<br/>DiagnosticReport, Observation"]
        bundle["BundleBuilder"]
        validator["BundleValidator"]
        bstore["BundleStore"]
    end

    subgraph ing_layer["ingestion"]
        readers["Readers: JSON, CSV, TXT"]
        cleaners["Cleaners: dates, gender,<br/>mrn, names, text, labs"]
        identity["IdentityResolver"]
        dedupe["Deduplicator"]
        audit["AuditLog"]
        ipipe["IngestionPipeline"]
    end

    db[("db: connection,<br/>schema.sql, repositories")]

    routers --> deps
    deps --> ssvc
    deps --> sumsvc
    deps --> bstore
    ssvc --> emb
    ssvc --> vstore
    ssvc --> lex
    ssvc --> rank
    ssvc --> filt
    chunk --> emb
    sumsvc --> ctx
    sumsvc --> anom
    sumsvc --> prov
    sumsvc --> guard
    sumsvc --> cache
    ctx --> bstore
    bundle --> mappers
    validator --> bundle
    bstore --> db
    cache --> db
    ipipe --> readers
    ipipe --> cleaners
    ipipe --> identity
    ipipe --> dedupe
    ipipe --> audit
    ipipe --> db
    mappers --> db
```

**Dependency rule:** arrows only point down the stack `api → search → summarization → fhir → ingestion → db`. Enforced with an import-linter contract in CI (`importlinter` layers contract).

## 4. Frontend architecture

```mermaid
flowchart TB
    subgraph routes["TanStack Router (Zod search params)"]
        rsearch["/ (SearchPage)<br/>?q&types&from&to&patient"]
        rpat["/patients (Directory)<br/>?q&page&size&sort&order&patient"]
        rqual["/quality (DataQuality)<br/>?tab&severity&page"]
    end

    subgraph features["features/*"]
        fsearch["search: SearchInput, FilterBar,<br/>ResultList, ResultCard"]
        fpat["patients: PatientDrawer, SummaryPanel,<br/>ResourceTable, DirectoryTable"]
        fqual["quality: KpiStrip, IssuesTable, AuditTable"]
    end

    subgraph data["Data layer"]
        hooks["queries.ts<br/>queryOptions factories + key factories"]
        qc[("QueryClient cache")]
        client["lib/api-client.ts<br/>fetch + AbortSignal + Zod parse<br/>ApiError(problem+json)"]
        schemas["features/*/schemas.ts<br/>Zod mirrors of the API contract"]
    end

    rsearch --> fsearch
    rsearch --> fpat
    rpat --> fpat
    rqual --> fqual
    fsearch --> hooks
    fpat --> hooks
    fqual --> hooks
    hooks <--> qc
    hooks --> client
    client --> schemas
    client -- "fetch /api/*" --> backend["FastAPI"]
```

State ownership: **URL** owns search query, filters, open patient, table paging. **TanStack Query** owns server data. **Component state** owns only ephemeral UI (popover open, input draft before debounce). No global store library.

## 5. Pipeline flow

```mermaid
flowchart LR
    A[("data/raw")] --> B["ingest<br/>read → clean → identity → dedupe"]
    B --> C[("patients, encounters,<br/>documents, lab_results,<br/>audit_log, quarantine")]
    C --> D["normalize<br/>map → bundle → validate"]
    D --> E[("fhir_bundles,<br/>fhir_resources,<br/>validation_issues")]
    D --> R1["reports/validation_report.json|md"]
    E --> F["summarize<br/>context → cache? → LLM → guardrails"]
    F --> G[("summary_cache")]
    E --> H["index<br/>chunk → embed → upsert"]
    G --> H
    H --> I[("Chroma: ehr_records")]
    G --> J["eval<br/>metrics report"]
    J --> R2["reports/eval_report.json|md"]
```

Every stage is idempotent: deterministic ids, `INSERT OR REPLACE`, Chroma `upsert`, cache keyed by content hash.

### 5.1 Sequence: `ehr-mip run-all`

```mermaid
sequenceDiagram
    autonumber
    actor Dev as Developer
    participant CLI as ehr-mip CLI
    participant IP as IngestionPipeline
    participant DB as SQLite
    participant FB as BundleBuilder + Validator
    participant SS as SummaryService
    participant LLM as Provider (Claude or Extractive)
    participant IX as Indexer
    participant VS as Chroma

    Dev->>CLI: run-all
    CLI->>DB: insert pipeline_runs(run_id, stage=ingest)
    CLI->>IP: run(data/raw)
    IP->>IP: read JSON, CSV, TXT into RawRecords
    IP->>IP: clean fields (audit each change)
    IP->>IP: resolve identities, dedupe
    IP->>DB: save patients, documents, labs, audit, quarantine
    CLI->>FB: build bundle per patient
    FB->>FB: map resources, model_validate, business rules
    FB->>DB: save bundles, resources, validation_issues
    FB-->>CLI: ValidationReport (write reports/*)
    CLI->>SS: summarize_all(concurrency=4)
    loop each patient
        SS->>DB: get cache(cache_key)
        alt cache hit
            DB-->>SS: ClinicalSummary
        else cache miss
            SS->>LLM: summarize(de-identified context)
            LLM-->>SS: ClinicalSummaryLLM
            SS->>SS: guardrails (words, grounding, confidence)
            SS->>DB: put cache
        end
    end
    CLI->>IX: index(bundles, summaries)
    IX->>IX: chunk + embed (batch 64)
    IX->>VS: upsert(ids, embeddings, metadatas, documents)
    CLI->>DB: update pipeline_runs(finished_at, stats)
    CLI-->>Dev: summary table (counts, timings)
```

## 6. Request flows

### 6.1 Sequence: real-time search

```mermaid
sequenceDiagram
    autonumber
    actor U as Clinician
    participant UI as SearchPage
    participant RQ as TanStack Query
    participant AC as api-client
    participant API as FastAPI /search
    participant S as SearchService
    participant E as Embedder
    participant V as Chroma
    participant L as BM25
    participant DB as SQLite

    U->>UI: types "high potassium kidney"
    UI->>UI: debounce 300 ms, min 2 chars, update URL ?q=
    UI->>RQ: useQuery(searchKeys.query(params))
    RQ->>AC: queryFn({signal})
    Note over RQ,AC: previous in-flight request aborted,<br/>previous results kept (placeholderData)
    AC->>API: POST /search?resource_type=..&date_from=.. {query}
    API->>API: validate (422 on bad input)
    API->>S: search(query, filters, top_k=5)
    S->>E: encode(query)
    E-->>S: vector (384 dims)
    S->>V: query(vector, n_results=30, where)
    V-->>S: chunks + distances
    opt mode = hybrid
        S->>L: score(query)
        L-->>S: lexical ranks
        S->>S: reciprocal rank fusion
    end
    S->>S: dedupe to best chunk per resource, take top 5
    S->>DB: hydrate patients + summary snippets (one IN query)
    DB-->>S: rows
    S-->>API: SearchResponse(took_ms)
    API-->>AC: 200 JSON + Server-Timing
    AC->>AC: Zod parse
    AC-->>RQ: data
    RQ-->>UI: render cards, live region "5 results, 41 ms"
```

### 6.2 Sequence: open patient drawer

```mermaid
sequenceDiagram
    autonumber
    actor U as Clinician
    participant UI as ResultCard / PatientDrawer
    participant RQ as TanStack Query
    participant API as FastAPI

    U->>UI: hover or focus result card
    UI->>RQ: prefetchQuery(patient detail), prefetchQuery(summary)
    RQ->>API: GET /patients/{key}
    RQ->>API: GET /patients/{key}/summary
    U->>UI: Enter or click
    UI->>UI: set URL ?patient={key} (drawer opens, focus moves to title)
    UI->>RQ: useQuery(detail), useQuery(summary), useQuery(resources)
    RQ-->>UI: cached detail + summary (instant)
    RQ->>API: GET /patients/{key}/resources
    API-->>RQ: 200 resources
    U->>UI: click evidence chip "DR · Feb 2"
    UI->>UI: switch to Records tab, highlight row
    U->>UI: open row
    UI->>RQ: useQuery(resource detail)
    RQ->>API: GET /resources/DiagnosticReport/{id}
    API-->>RQ: 200 ResourceDetail
    U->>UI: Esc
    UI->>UI: remove ?patient, restore focus to card
```

### 6.3 Sequence: summary generation with cache, guardrails and fallback

```mermaid
sequenceDiagram
    autonumber
    participant SS as SummaryService
    participant C as SummaryCache
    participant CB as ContextBuilder
    participant AD as AnomalyDetector
    participant AP as AnthropicProvider
    participant EP as ExtractiveProvider
    participant G as Guardrails

    SS->>C: get(sha256(patient_key, bundle_hash, prompt_version, model))
    alt hit and not force
        C-->>SS: ClinicalSummary (cached=true)
    else miss or force
        SS->>AD: detect(bundle)
        AD-->>SS: rule anomalies
        SS->>CB: build(bundle, anomalies)
        CB-->>SS: de-identified context (no name, MRN, DOB)
        alt API key present
            SS->>AP: messages.parse(output_format=ClinicalSummaryLLM)
            alt success
                AP-->>SS: parsed output
            else 4 failed attempts (429, 5xx, timeout)
                SS->>EP: summarize(context)
                EP-->>SS: extractive output
            end
        else no key
            SS->>EP: summarize(context)
            EP-->>SS: extractive output
        end
        SS->>G: enforce(output, bundle, anomalies)
        opt word_count > 200 and provider = anthropic
            G->>AP: retry once with shorten instruction
            AP-->>G: shorter output
        end
        G-->>SS: ClinicalSummary (grounded, ≤ 200 words, confidence)
        SS->>C: put(summary)
    end
```

## 7. Deployment

```mermaid
flowchart LR
    subgraph compose["docker compose"]
        web["web<br/>nginx:alpine<br/>:8080"]
        api["api<br/>python:3.12-slim + uv<br/>:8000<br/>AUTO_BOOTSTRAP=true"]
        vol[("volume: app-data<br/>ehr_mip.db, chroma/, hf-cache/")]
        redis["redis<br/>redis:7-alpine<br/>profile: redis<br/>no published port"]
    end
    user(["Browser"]) -- ":8080" --> web
    web -- "/api → api:8000" --> api
    api --- vol
    api -. "optional" .-> redis
    prom["Prometheus (optional)"] -. "scrape /metrics" .-> api
    api -- "HTTPS (optional)" --> claude["Claude API"]
```

- `api` image pre-downloads the embedding model in a build layer and runs the pipeline on start if the DB is empty (`AUTO_BOOTSTRAP=true`).
- `web` image builds the Vite app and serves `dist/` with an nginx `location /api/ { proxy_pass http://api:8000/; }`.
- Health checks: `api` uses `GET /ready`; `web` depends on `api` healthy.

## 8. Caching architecture

Caches are layered. Each has one owner, a clear key and an explicit invalidation rule. SQLite is the system of record for summaries (the brief asks for a file or SQLite cache); Redis is an optional shared backend for short-lived caches and rate limit counters, selected with `CACHE_BACKEND=memory|redis`.

```mermaid
flowchart LR
    subgraph client["Browser"]
        rq["TanStack Query cache<br/>staleTime per query"]
        http["HTTP cache<br/>ETag / 304"]
    end
    subgraph server["API process"]
        l1["Search response cache<br/>TTL 60 s, LRU 512<br/>memory or Redis"]
        warm["Warm singletons<br/>embedder, Chroma client,<br/>BM25 index"]
        sc["Summary cache<br/>SQLite summary_cache<br/>(system of record)"]
        rl["Rate limit counters<br/>memory or Redis"]
    end
    subgraph llm["Claude API"]
        pc["Prompt caching<br/>static system prompt + example"]
    end
    rq --> http --> l1
    l1 -- miss --> warm
    sc -- miss --> pc
```

| Cache | Key | TTL / lifetime | Invalidation | Backend |
|---|---|---|---|---|
| TanStack Query | query key factory (`04-API-CONTRACT.md` §11.1) | staleTime per query | mutation `setQueryData` / `invalidateQueries` | browser memory |
| HTTP ETag | `"{bundle_hash}:{prompt_version}"` | until data changes | new hash | browser |
| Search responses | `search:{index_version}:{sha256(normalized query, filters, top_k, mode)}` | 60 s | `index_version` bumps on every `ehr-mip index` run, so old keys die naturally. It is the count of finished `index` runs in `pipeline_runs`, so the API process sees a reindex done by the CLI; the API reloads Chroma and BM25 when it changes | in-process `cachetools.TTLCache` or Redis |
| Patient detail / resources | `patient:{bundle_hash}:{key}` | 5 min | new bundle hash | same as above |
| Summaries | `sha256(patient_key, bundle_hash, prompt_version, model)` | permanent | content-addressed: new data or prompt gives a new key | SQLite |
| Embedder, Chroma, BM25 | process lifetime | until restart or reindex signal | `POST /pipeline/runs` (admin) reloads BM25 and bumps `index_version` | memory |
| Rate limit counters | `rl:{route}:{ip}` | window length | automatic | memory or Redis |
| LLM prompt caching | provider side, static system prompt and few-shot block marked cacheable (only effective once that prefix exceeds the model's minimum cacheable length) | provider TTL | prompt version change | Anthropic |

Cache values never contain PHI in Redis: search cache stores result ids, scores, snippets and is keyed by a hash, and Redis is internal-only with no persistence. Every cache emits hit and miss counters to `/metrics`.

### 8.1 Sequence: search with response cache

```mermaid
sequenceDiagram
    autonumber
    participant API as /search router
    participant C as SearchCache (memory or Redis)
    participant S as SearchService
    API->>API: normalize query (trim, lowercase, collapse spaces), sort filter lists
    API->>C: get(search:{index_version}:{hash})
    alt hit
        C-->>API: cached SearchResponse
        API->>API: set took_ms (actual), header X-Cache: HIT
    else miss
        API->>S: search(...)
        S-->>API: SearchResponse
        API->>C: set(key, response, ttl=60)
        API->>API: header X-Cache: MISS
    end
```

## 9. Cross-cutting concerns

| Concern | Approach |
|---|---|
| Configuration | `pydantic-settings` `Settings` loaded once, injected via `Depends(get_settings)`; frontend reads only `import.meta.env.VITE_*` (none required with proxy) |
| Errors | Domain exceptions → RFC 9457 problem+json (see `04-API-CONTRACT.md` section 2.3) |
| Logging | structlog JSON: `ts, level, event, request_id, route, status, duration_ms, patient_key?`. Never names, MRNs, DOB, note text |
| Tracing headers | `X-Request-ID` (echoed or generated), `Server-Timing: embed;dur=.., vector;dur=.., hydrate;dur=..` |
| Concurrency | SQLite WAL, one connection per request via dependency; Chroma client and embedder are app-scoped singletons on `app.state` |
| Startup | FastAPI lifespan: load settings, open SQLite, load and warm embedder, open Chroma collection, build BM25 index |
| Security | Full controls in `09-SECURITY.md`: headers, rate limits, input limits, redaction, admin token, hardened containers |
| Privacy | Synthetic data; LLM sees age, sex and clinical text only |
| Metrics | `prometheus-fastapi-instrumentator` at `/metrics` plus custom counters: search latency histogram, cache hits/misses per cache, LLM calls/tokens/latency, guardrail interventions |
| Shutdown | Lifespan exit closes SQLite, flushes logs, cancels in-flight summary tasks; Uvicorn `--timeout-graceful-shutdown 10` |
| Feature flags | Settings booleans (`SEARCH_MODE`, `INDEX_OBSERVATIONS`, `ENABLE_ADMIN_ENDPOINTS`, `CACHE_BACKEND`), exposed read-only in `/ready` so the UI can adapt |

## 10. Repository layout

```
ehr-media-intelligence/
├── AGENTS.md  CLAUDE.md  README.md  LICENSE
├── Makefile  docker-compose.yml  .env.example  .gitignore  .pre-commit-config.yaml
├── .github/ (workflows/ci.yml, security.yml, eval.yml; dependabot.yml; CODEOWNERS; pull_request_template.md; ISSUE_TEMPLATE/)
├── .editorconfig  .commitlintrc.json  CHANGELOG.md  SECURITY.md
├── data/raw/ (ehr_export.json, lab_results.csv, notes/*.txt, _ground_truth.json)
├── data/generated/            # gitignored
├── reports/                   # generated reports (samples committed)
├── scripts/ (generate_synthetic_data.py, export_openapi.py)
├── docs/ (01..10 *.md, openapi.json, AI_SYSTEM_CARD.md, WRITEUP.md, WRITEUP.pdf, decisions/ADR-*.md, eval/, ux/, design-refs/)
├── backend/
│   ├── pyproject.toml  uv.lock  requirements.txt  Dockerfile
│   ├── src/ehr_mip/
│   │   ├── config.py  errors.py  logging.py  cli.py
│   │   ├── db/ (schema.sql, connection.py, repositories.py)
│   │   ├── ingestion/ (models.py, audit.py, identity.py, dedupe.py, pipeline.py, readers/, cleaners/)
│   │   ├── fhir/ (codes.py, ids.py, bundle.py, validator.py, store.py, mappers/)
│   │   ├── summarization/ (schemas.py, context.py, anomalies.py, guardrails.py, cache.py, service.py, evaluate.py, telemetry.py, feedback.py, providers/, prompts/v1/)
│   │   ├── search/ (chunker.py, embedder.py, vector_store.py, lexical.py, ranking.py, filters.py, indexer.py, service.py)
│   │   ├── cache/ (backend.py: CacheBackend protocol, MemoryBackend, RedisBackend)
│   │   ├── observability/ (metrics.py, log_redaction.py)
│   │   └── api/ (main.py, deps.py, errors.py, middleware.py, security_headers.py, rate_limit.py, schemas/, routers/)
│   └── tests/ (conftest.py, fixtures/ incl. golden/, unit/, integration/, perf/, contract/, security/)
└── frontend/
    ├── package.json  vite.config.ts  components.json  eslint.config.js  playwright.config.ts  lighthouserc.json  Dockerfile  nginx.conf
    ├── .storybook/
    ├── e2e/
    └── src/ (main.tsx, index.css, router.tsx, app/, routes/, features/{search,patients,quality}/, components/{ui,common}/, lib/, test/)
```

## 11. Architecture decision records

Write each as `docs/decisions/ADR-00N-*.md` (context, decision, consequences).

| ADR | Decision | Rejected | Reason |
|---|---|---|---|
| 001 | `fhir.resources` 8.x using sub-package `R4B` | `fhir.resources` 6.x (R4 on Pydantic v1); `fhirclient` | Brief requires Pydantic v2. Since 7.0 the package ships R4B, not pure R4. R4B keeps Patient, Encounter, DocumentReference, DiagnosticReport, Observation and Bundle structurally compatible with R4. Optional HL7 validator run with `-version 4.0.1` |
| 002 | ChromaDB | FAISS | Native metadata filters (type, date) and persistence |
| 003 | Search result unit = one FHIR resource (best chunk) | Raw chunks | Brief asks for "patient record matches" |
| 004 | UUIDv5 ids from stable source facts | uuid4 | Idempotent runs, stable cache keys and vector ids |
| 005 | De-identified LLM context | Whole bundle | Privacy, fewer tokens, smaller hallucination surface |
| 006 | Extractive fallback summarizer | Fail without key | System runs offline for reviewers |
| 007 | Conservative identity resolution | Aggressive fuzzy merge | Wrong merges are clinically dangerous |
| 008 | Ambiguous dates parsed as US MM/DD with warning audit | Silent guess | Epic US source; every guess visible |
| 009 | stdlib `sqlite3` + repositories | SQLAlchemy ORM | Small schema, transparent SQL, fewer deps |
| 010 | TanStack Router with Zod search params | React Router | Typed, validated URL state for shareable searches |
| 011 | Redis optional, memory TTL cache default | Redis required | Single process and small data; Redis adds value only when scaling to several API replicas. Interface `CacheBackend` keeps the switch to one setting |
| 012 | slowapi for rate limiting | Custom middleware | Mature, supports memory and Redis storage, standard headers |
