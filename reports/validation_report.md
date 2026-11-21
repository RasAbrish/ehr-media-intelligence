# FHIR validation report

Generated 2026-11-21T13:50:32+00:00. One FHIR R4 (R4B package) Bundle per patient, validated with `fhir.resources` and the business rules in `docs/05-ALGORITHMS.md` section 2.2. Patients are identified by key only.

## Summary

| Measure | Value |
|---|---|
| Bundles | 60 |
| Valid bundles (no errors) | 60 |
| Errors | 0 |
| Warnings | 4 |
| Info | 2 |

## Resources

| Resource type | Count |
|---|---|
| DiagnosticReport | 155 |
| DocumentReference | 90 |
| Encounter | 97 |
| Observation | 291 |
| Patient | 60 |

## Issues by rule

| Rule | Severity | Count |
|---|---|---|
| `encounter.missing` | info | 2 |
| `patient.identity_conflict` | warning | 4 |

## Invalid bundles

None. Every bundle passed schema and reference checks.

## Errors and warnings

| Severity | Rule | Resource | Path | Message |
|---|---|---|---|---|
| warning | `patient.identity_conflict` | Patient/824ffb52 | `Patient.meta.tag` | Records under this MRN belong to more than one person; review the identity. |
| warning | `patient.identity_conflict` | Patient/890b1081 | `Patient.meta.tag` | Records under this MRN belong to more than one person; review the identity. |
| warning | `patient.identity_conflict` | Patient/320afa77 | `Patient.meta.tag` | Records under this MRN belong to more than one person; review the identity. |
| warning | `patient.identity_conflict` | Patient/76f99514 | `Patient.meta.tag` | Records under this MRN belong to more than one person; review the identity. |
