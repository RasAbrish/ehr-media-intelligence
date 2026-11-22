/** System endpoints (docs/04 section 4). */
import { z } from "@/lib/zod";

import { RunStatusSchema, SearchModeSchema, SummaryProviderSchema } from "@/lib/contract-enums";

const CheckSchema = z.strictObject({ ok: z.boolean(), detail: z.string() });
const BackendSchema = z.enum(["memory", "redis"]);

export const HealthResponseSchema = z.strictObject({
  status: z.literal("ok"),
  version: z.string(),
});

export const LastRunSchema = z.strictObject({
  run_id: z.string(),
  finished_at: z.string().nullable(),
  status: RunStatusSchema,
});

export const ReadyResponseSchema = z.strictObject({
  status: z.enum(["ready", "degraded", "not_ready"]),
  checks: z.strictObject({
    sqlite: CheckSchema,
    vector_store: CheckSchema.extend({ chunks: z.number().int() }),
    embedder: CheckSchema.extend({ model: z.string() }),
    llm: CheckSchema.extend({ provider: SummaryProviderSchema, model: z.string().nullable() }),
  }),
  counts: z.strictObject({
    patients: z.number().int(),
    resources: z.number().int(),
    summaries: z.number().int(),
    chunks: z.number().int(),
  }),
  last_run: LastRunSchema.nullable(),
  flags: z.strictObject({
    search_mode: SearchModeSchema,
    index_observations: z.boolean(),
    admin_enabled: z.boolean(),
    cache_backend: BackendSchema,
    feedback_enabled: z.boolean(),
  }),
  cache: z.strictObject({
    backend: BackendSchema,
    ok: z.boolean(),
    index_version: z.number().int(),
  }),
});

export const StatsResponseSchema = z.strictObject({
  patients: z.number().int(),
  resources_by_type: z.strictObject({
    Encounter: z.number().int(),
    DocumentReference: z.number().int(),
    DiagnosticReport: z.number().int(),
    Observation: z.number().int(),
  }),
  searchable_records: z.number().int(),
  summaries: z.number().int(),
  last_pipeline_run_at: z.string().nullable(),
});

export const PipelineRunAcceptedSchema = z.strictObject({
  run_id: z.string(),
  status: RunStatusSchema,
  stages: z.array(z.enum(["ingest", "normalize", "summarize", "index"])),
});

export type ReadyResponse = z.infer<typeof ReadyResponseSchema>;
