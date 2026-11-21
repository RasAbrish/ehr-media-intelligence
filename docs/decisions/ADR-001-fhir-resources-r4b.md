# ADR-001: Use fhir.resources 8.x with the R4B sub-package

- **Status:** Accepted
- **Date:** 2026-11-21

## Context

The brief asks for HL7 FHIR R4 output validated with `fhir.resources`, and the rest of the backend uses Pydantic v2. The package only offers R4 models on Pydantic v1, in its 6.x line. Since 7.0 it ships R4B on Pydantic v2, and R5 as the default. R4B (4.3.0) is a small revision of R4 (4.0.1): the resources this project uses (Patient, Encounter, DocumentReference, DiagnosticReport, Observation, Bundle) are structurally the same apart from additions this project does not use.

Installed and verified: `fhir.resources` 8.3.0 with Pydantic 2.14, imports from `fhir.resources.R4B.*`.

## Decision

Map and validate against `fhir.resources.R4B` and describe the output as FHIR R4 (R4B package). Use only elements that exist with the same meaning in R4 4.0.1.

Two behaviors of the library shaped the validator:

1. **Value sets are not enforced.** Version 8 checks code *format* only, so `Patient.gender = "F"` passes schema validation. The validator adds a `code.invalid` rule for the required bindings the project relies on: gender, resource `status`, `docStatus` and `Bundle.type`.
2. **Bundle validation is deep.** `Bundle.model_validate` validates every entry resource and reports locations such as `entry.3.resource.status`, which the validator turns into FHIR paths like `Observation.status`.

## Alternatives rejected

- **`fhir.resources` 6.x (R4 on Pydantic v1).** It would split the codebase across two Pydantic major versions.
- **`fhirclient`.** It is a client library for FHIR servers, not a validating model library.
- **Hand-written models.** They would duplicate the specification and miss the cardinality and type checks.

## Consequences

- Output validates as R4B. For strict R4 conformance the optional HL7 validator target (`make validate-official`, P2) runs the official Java validator with `-version 4.0.1`.
- Value-set coverage is limited to the bindings listed above. Extensible bindings such as LOINC document types are not checked locally.
- A later move to R5 would change the import path and a few mappers (for example `DocumentReference.context` and `Attachment.size`), but not the clean IR.
