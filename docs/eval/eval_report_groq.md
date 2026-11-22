# Summary evaluation report

Generated 2026-11-22T23:16:31+00:00. Provider: groq; model: openai/gpt-oss-120b; prompt `v1`.

## Gates

| Gate | Result |
|---|---|
| schema disclaimer length | pass |
| grounding final | pass |
| diagnosis support | FAIL |
| high anomaly recall | pass |
| golden required facts | FAIL |
| adversarial | FAIL |
| ground truth recall | FAIL |

Overall: **FAIL**

## Synthetic set (60 patients, 0 failed)

| Metric | Value | Target |
|---|---|---|
| Schema validity | 100.0% | 100% |
| Length compliance (≤ 200 words) | 100.0% | 100% |
| Disclaimer present | 100.0% | 100% |
| Grounding before guardrails | 100.0% | report |
| Grounding final | 100.0% | 100% |
| Diagnosis support | 81.2% | ≥ 95% |
| High anomaly recall | 100.0% | 100% |
| Guardrail intervention rate | 28.3% | report |
| Ground truth recall | 82.3% (79/96) | ≥ 85% |

## Golden set

| Case | Words | Confidence | Result | Notes |
|---|---|---|---|---|
| golden-breast | 59 | high 0.85 | FAIL | diagnosis 'breast mass' |
| golden-ckd | 52 | high 0.85 | FAIL | chief concern keyword |
| golden-hypothyroid | 52 | medium 0.65 | FAIL | chief concern keyword |
| golden-pe | 57 | high 0.85 | FAIL | chief concern keyword |
| golden-pneumonia | 47 | high 0.85 | pass | none |

## Adversarial set

| Case | Words | Confidence | Result | Notes |
|---|---|---|---|---|
| adversarial-conflict | 36 | low 0.40 | FAIL | identity_flagged |
| adversarial-injection | 35 | low 0.40 | pass | none |
| adversarial-labs-only | 22 | low 0.30 | FAIL | forbidden: hypokalemia |
| adversarial-long-note | 35 | low 0.40 | pass | none |
| adversarial-sparse | 34 | low 0.30 | pass | none |

## Model calls in this run

Calls 0, tokens 0 in / 0 out, estimated cost $0.0000, p95 latency n/a ms, fallbacks 0. Cached summaries make no calls.

## Manual review

Ten random summaries are scored 1 to 5 by a person in `docs/eval/manual_review_<model>.md` (gate: mean ≥ 4). This report does not score them.

## Ground truth conditions not found

- S-002: hyponatremia
- S-008: breast mass
- S-009: hyperlipidemia
- S-012: hyponatremia
- S-018: breast mass
- S-019: hyperlipidemia
- S-022: hyponatremia
- S-028: breast mass
- S-032: hyponatremia
- S-038: breast mass
- S-039: hyperlipidemia
- S-042: hyponatremia
- S-048: breast mass
- S-049: hyperlipidemia
- S-052: hyponatremia
- S-058: breast mass
- S-059: hyperlipidemia

## Other findings

- 0f6e25ff: unsupported diagnosis 'Emphysematous changes of lung'
- 3545f026: unsupported diagnosis 'E. coli urinary infection'
- 4603a76a: unsupported diagnosis 'E. coli urinary tract infection'
- 4a95631a: unsupported diagnosis 'Invasive ductal carcinoma of left breast, ER/PR positive, HER2 negative'
- 5412eee9: unsupported diagnosis 'Reduced left ventricular ejection fraction (30%)'
- 6e2114f3: unsupported diagnosis 'Elevated LDL cholesterol'
- 73c422bf: unsupported diagnosis 'Urosepsis'
- 73c422bf: unsupported diagnosis 'Elevated lactate'
- 78382737: unsupported diagnosis 'Hyperlipidemia (elevated LDL)'
- 8167427c: unsupported diagnosis 'Invasive ductal carcinoma of left breast'
- 8167427c: unsupported diagnosis 'Hormone receptor positive breast cancer (ER+, PR+, HER2-)'
- 824ffb52: unsupported diagnosis 'Elevated LDL cholesterol'
- 91f0d472: unsupported diagnosis 'Sepsis from urinary source (urosepsis)'
- 91f0d472: unsupported diagnosis 'E. coli urinary tract infection'
- a6f98525: unsupported diagnosis 'Urosepsis'
- a6f98525: unsupported diagnosis 'Escherichia coli urinary infection'
- dede8ad9: unsupported diagnosis 'Invasive ductal carcinoma of left breast'
- dede8ad9: unsupported diagnosis 'Hormone receptor positive (ER+, PR+), HER2 negative tumor'
- e817ac40: unsupported diagnosis 'Invasive ductal carcinoma, Nottingham grade 2, ER+/PR+, HER2-'
