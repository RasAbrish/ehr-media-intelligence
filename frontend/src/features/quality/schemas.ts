/** Data quality overview (docs/04 section 8.1, P1): schema only, used by the contract test. */
import { z } from "zod";

import { LastRunSchema } from "@/lib/system-schemas";

const BySeverity = z.strictObject({
  info: z.number().int(),
  warning: z.number().int(),
  error: z.number().int(),
});
const RateOrNull = z.number().nullable();

export const QualityOverviewSchema = z.strictObject({
  ingestion: z.strictObject({
    records_read: z.number().int(),
    by_format: z.strictObject({
      json: z.number().int(),
      csv: z.number().int(),
      txt: z.number().int(),
    }),
    patients: z.number().int(),
    documents: z.number().int(),
    lab_results: z.number().int(),
    exact_duplicates_removed: z.number().int(),
    near_duplicates_removed: z.number().int(),
    identities_merged: z.number().int(),
    identity_conflicts: z.number().int(),
    quarantined: z.number().int(),
    audit_by_severity: BySeverity,
    top_rules: z.array(z.strictObject({ rule: z.string(), count: z.number().int() })),
  }),
  validation: z.strictObject({
    bundles: z.number().int(),
    valid_bundles: z.number().int(),
    issues_by_severity: BySeverity,
    top_codes: z.array(z.strictObject({ code: z.string(), count: z.number().int() })),
  }),
  summaries: z.strictObject({
    total: z.number().int(),
    by_provider: z.strictObject({ anthropic: z.number().int(), extractive: z.number().int() }),
    avg_word_count: z.number(),
    max_word_count: z.number().int(),
    confidence: z.strictObject({
      low: z.number().int(),
      medium: z.number().int(),
      high: z.number().int(),
    }),
    guardrail_interventions: z.number().int(),
    llm: z.strictObject({
      calls: z.number().int(),
      fallback_calls: z.number().int(),
      failed_calls: z.number().int(),
      input_tokens: z.number().int(),
      output_tokens: z.number().int(),
      cost_usd_estimate: z.number(),
      p95_latency_ms: z.number(),
    }),
    feedback: z.strictObject({
      helpful: z.number().int(),
      not_helpful: z.number().int(),
      helpful_rate: RateOrNull,
      by_prompt_version: z.array(
        z.strictObject({
          prompt_version: z.string(),
          helpful_rate: RateOrNull,
          votes: z.number().int(),
        }),
      ),
    }),
  }),
  last_run: LastRunSchema.nullable(),
});
