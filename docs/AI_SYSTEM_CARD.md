# AI system card: patient clinical summary

The design behind this card is in [10-AI-DESIGN.md](10-AI-DESIGN.md). This card reports what is built and what has been measured.

> **Evaluation status.** Only the offline extractive provider has been evaluated on this repository. The Claude provider is implemented and tested with a fake provider. It has not been run against the real API, so its quality, cost and latency are unknown.

| Item | Value |
|---|---|
| Feature | Patient clinical summary: chief concern, key diagnoses, recent media, anomalies and overview |
| Intended users | Licensed clinicians reviewing records |
| Intended use | Faster orientation to a patient's existing documents, with a link to each source |
| Out of scope | Diagnosis, triage, treatment, billing codes, patient-facing text, real patient data |
| Model | Claude, small tier (`LLM_MODEL`, default `claude-haiku-5-5`), effort `low`, structured output, no sampling parameters |
| Fallback | Deterministic extractive summarizer, used without a key, when a call fails or is refused, and when the daily token budget is spent |
| Prompt | Versioned files, currently `v1`. A released version is never edited |
| Owner and version | The repository owner. Prompt version and model id are stored on every summary |

## Inputs

Age, sex, record texts (truncated), lab lines and rule-based anomalies, newest first, within about 6,000 tokens.

The patient's name parts, MRN forms and birth date are removed from the text, along with common formats of phone number, street address, email address and SSN. Author fields are left out. This is **not HIPAA Safe Harbor de-identification**: record dates are kept, ages over 89 are not grouped, and other people's names inside note text are not detected ([ADR-005](decisions/ADR-005-deidentified-llm-context.md)).

## Outputs

A validated `ClinicalSummaryLLM` object with at most 200 words, evidence ids on its claims, a confidence level with its reason, guardrail notes and a fixed disclaimer.

## Safeguards

- **Before the call:** identifier scrubbing, removal of instruction-like text, escaped record text inside tags, a system prompt that treats records as data, and no tools.
- **After the call:** schema validation, removal of uncited or wrongly cited items, a check of each diagnosis against its cited text, restoration of missing high severity anomalies and a word limit.
- **Confidence:** lowered by each guardrail intervention and capped for sparse records, identity conflicts, invalid bundles and extractive output.
- **In the interface:** AI label, disclaimer, provider and prompt version, fallback reason, evidence links and feedback stored per prompt version.
- **Operations:** a summary cache, a daily token budget and call telemetry without content.

## Evaluation

Provider `extractive`, prompt `v1`, 60 synthetic patients ([report](../reports/eval_report.md), reproduce with `make eval`).

| Metric | Result | Gate |
|---|---|---|
| Schema, length and disclaimer | 100% | 100% |
| Final grounding | 100% | 100% |
| Diagnosis support | 100% | at least 95% |
| High anomaly recall | 100% | 100% |
| Ground truth recall | 87.5% (84 of 96) | at least 85% |
| Golden set | 5 of 5 pass | all |
| Adversarial set, including prompt injection | 5 of 5 pass | all |
| Guardrail intervention rate | 0% | reported |
| Manual review | **Pending.** A person has to score the [10 sampled summaries](eval/manual_review_extractive.md) | mean of at least 4 of 5 |

Grounding and support are close to guaranteed for an extractive provider, because it only copies from the records. These results say little about how a language model would score.

## Known limitations

- **Systematic misses.** The extractive provider misses all 6 expected cases of hyponatremia and 6 of the 12 of hyperlipidemia. These are all 12 of its recall misses.
- **Context budget.** Older facts beyond the budget are not seen.
- **Wording.** Synonyms can lower the diagnosis support score of a correct diagnosis.
- **Text only.** Images are not read.
- **Fragments.** Extractive summaries read as copied fragments and always report low confidence.
- **No regenerate.** Regenerating from the interface is a P2 feature and is not built.
- **Synthetic, self-authored data.** The generator, dictionary and golden set come from the same project, so the scores are optimistic. No clinician has reviewed the output.

## Human oversight

The summary never changes a record. Clinicians can open each cited source and mark a summary helpful or not helpful with a reason.
