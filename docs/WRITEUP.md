# EHR Media Intelligence Platform: write-up

A pipeline that turns messy EHR exports into validated FHIR R4, summaries that cite their sources and a search interface for clinicians. All data is synthetic, and everything runs without an API key.

## Tradeoffs and why

- **R4B package for R4.** It is the only R4 family in `fhir.resources` on Pydantic v2. The mappers use only elements with the same meaning in R4.
- **Chroma over FAISS.** Type and date filters plus persistence, in process. The cost is one node and advisories to track.
- **Local MiniLM over an embedding API.** Records stay on the machine, at no cost and offline. A clinical embedding model would likely rank better.
- **Standard library SQLite.** Explicit SQL and no service. Production with several replicas needs PostgreSQL.
- **Conservative identity.** Different MRNs merge only on exact name and birth date, and conflicts are shown. Missed merges are accepted to avoid wrong ones.
- **US date policy.** An ambiguous `03/04/2025` is read as March 4 with an audit warning.
- **Small Claude tier with guardrails.** Cheap enough for one summary per patient. Code, not the model, enforces grounding, length and confidence.
- **Extractive fallback.** The product works without a key and when a call fails, with lower recall and plainer text.

## Security and AI design choices

- **De-identified context:** age, sex and scrubbed text. It is not Safe Harbor, because dates and other people's names can remain.
- **Prompt injection:** records are escaped data, instruction-like text is removed, the model has no tools and an adversarial test covers it.
- **API and runtime:** rate limits, security headers, input limits, logs without PHI and hardened containers.
- **Eval gates and feedback:** versioned prompts, golden and adversarial gates run by `make eval` (the GitHub workflows are switched off, as no hosted runner is available), and clinician votes stored per prompt version.

## With more time

SMART on FHIR authentication, role-based access and an access audit. Clinical NER (scispaCy or MedCAT) with SNOMED coding. OCR for scanned PDFs. Practitioner and Organization resources. A cross-encoder reranker, and clinical synonyms for the Newest order, which matches exact words today. A HAPI FHIR server. An evaluation with clinicians on real model output.

## FHIR and clinical concepts researched

- **Bundles:** `collection` versus transaction types, and `urn:uuid` references that resolve inside the Bundle.
- **Documents:** DocumentReference for notes, DiagnosticReport for imaging, pathology and lab reports, LOINC document codes and v2-0074 report sections.
- **Labs:** Observation interpretation codes, reference ranges, UCUM units and critical values.
- **Identity:** AdministrativeGender, and `use=old` identifiers for merged MRNs.
- **Versions:** where R4 and R4B differ, and that the library does not enforce value sets, so the validator does.

## How summary quality was validated

`make eval` on 60 synthetic patients plus 5 golden and 5 adversarial cases, with the extractive provider and prompt v1:

| Schema, length, disclaimer | Grounding | Diagnosis support | High anomaly recall | Ground truth recall | Golden, adversarial | Guardrail interventions |
|---|---|---|---|---|---|---|
| 100% | 100% | 100% | 100% | 87.5% (84 of 96) | 5 of 5, 5 of 5 | 0% |

The 12 misses are systematic: hyponatremia (6) and hyperlipidemia (6). Grounding and support are easy for a provider that copies from the records, and the data and dictionary share an author, so these scores are optimistic. The Claude path is tested with a fake provider and **has not been run against the real API**. The **manual review of 10 summaries is pending** and has no scores yet.
