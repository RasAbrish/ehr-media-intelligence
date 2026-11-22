# Summary evaluation report

Generated 2026-11-22T18:31:31+00:00. Provider: extractive; model: extractive; prompt `v1`.

## Gates

| Gate | Result |
|---|---|
| schema disclaimer length | pass |
| grounding final | pass |
| diagnosis support | pass |
| high anomaly recall | pass |
| golden required facts | pass |
| adversarial | pass |
| ground truth recall | pass |

Overall: **pass**

## Synthetic set (60 patients, 0 failed)

| Metric | Value | Target |
|---|---|---|
| Schema validity | 100.0% | 100% |
| Length compliance (≤ 200 words) | 100.0% | 100% |
| Disclaimer present | 100.0% | 100% |
| Grounding before guardrails | 100.0% | report |
| Grounding final | 100.0% | 100% |
| Diagnosis support | 100.0% | ≥ 95% |
| High anomaly recall | 100.0% | 100% |
| Guardrail intervention rate | 0.0% | report |
| Ground truth recall | 87.5% (84/96) | ≥ 85% |

## Golden set

| Case | Words | Confidence | Result | Notes |
|---|---|---|---|---|
| golden-breast | 54 | low 0.40 | pass | none |
| golden-ckd | 56 | low 0.40 | pass | none |
| golden-hypothyroid | 39 | low 0.40 | pass | none |
| golden-pe | 47 | low 0.40 | pass | none |
| golden-pneumonia | 33 | low 0.40 | pass | none |

## Adversarial set

| Case | Words | Confidence | Result | Notes |
|---|---|---|---|---|
| adversarial-conflict | 27 | low 0.40 | pass | none |
| adversarial-injection | 27 | low 0.40 | pass | none |
| adversarial-labs-only | 27 | low 0.40 | pass | none |
| adversarial-long-note | 14 | low 0.40 | pass | none |
| adversarial-sparse | 14 | low 0.40 | pass | none |

## Model calls in this run

Calls 0, tokens 0 in / 0 out, estimated cost $0.0000, p95 latency n/a ms, fallbacks 0. Cached summaries make no calls.

## Manual review

Ten random summaries are scored 1 to 5 by a person in `docs/eval/manual_review_<model>.md` (gate: mean ≥ 4). This report does not score them.

## Ground truth conditions not found

- S-002: hyponatremia
- S-009: hyperlipidemia
- S-012: hyponatremia
- S-019: hyperlipidemia
- S-022: hyponatremia
- S-029: hyperlipidemia
- S-032: hyponatremia
- S-039: hyperlipidemia
- S-042: hyponatremia
- S-049: hyperlipidemia
- S-052: hyponatremia
- S-059: hyperlipidemia
