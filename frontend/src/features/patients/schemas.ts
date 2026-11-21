/** Patient, summary, resource and feedback contracts (docs/04 sections 6, 7 and 9a). */
import { z } from "zod";

import {
  EvidenceRefSchema,
  pageSchema,
  PatientRefSchema,
  ResourceRefSchema,
} from "@/lib/common-schemas";
import {
  AnomalySeveritySchema,
  ConfidenceLevelSchema,
  InterpretationSchema,
  SeveritySchema,
  SummaryProviderSchema,
} from "@/lib/contract-enums";

const CountsSchema = z.strictObject({
  Encounter: z.number().int(),
  DocumentReference: z.number().int(),
  DiagnosticReport: z.number().int(),
  Observation: z.number().int(),
});

export const PatientListItemSchema = PatientRefSchema.extend({
  last_activity: z.string().nullable(),
  resource_count: z.number().int(),
  has_summary: z.boolean(),
  chief_concern: z.string().nullable(),
  anomaly_counts: z.strictObject({
    high: z.number().int(),
    moderate: z.number().int(),
    low: z.number().int(),
  }),
});
export const PatientPageSchema = pageSchema(PatientListItemSchema);

export const PatientDetailSchema = PatientRefSchema.extend({
  family_name: z.string().nullable(),
  given_names: z.array(z.string()),
  identifiers: z.array(
    z.strictObject({ system: z.string(), value: z.string(), use: z.enum(["usual", "old"]) }),
  ),
  phone: z.string().nullable(),
  address: z
    .strictObject({
      line: z.string().nullable(),
      city: z.string().nullable(),
      state: z.string().nullable(),
      postal_code: z.string().nullable(),
    })
    .nullable(),
  bundle: z.strictObject({
    is_valid: z.boolean(),
    error_count: z.number().int(),
    warning_count: z.number().int(),
    bundle_hash: z.string(),
  }),
  counts: CountsSchema,
  first_activity: z.string().nullable(),
  last_activity: z.string().nullable(),
  data_quality: z.strictObject({
    audit_entries: z.number().int(),
    warnings: z.number().int(),
    errors: z.number().int(),
  }),
});

const IssueSchema = z.strictObject({
  severity: SeveritySchema,
  code: z.string(),
  message: z.string(),
});

export const PatientResourceItemSchema = ResourceRefSchema.extend({
  status: z.string(),
  encounter_id: z.string().nullable(),
  summary_line: z.string().nullable(),
  interpretation: InterpretationSchema.nullable(),
  issues: z.array(IssueSchema),
});

export const PatientResourcesResponseSchema = z.strictObject({
  patient_key: z.string(),
  total: z.number().int(),
  items: z.array(PatientResourceItemSchema),
});

export const ClinicalSummaryResponseSchema = z.strictObject({
  patient_key: z.string(),
  chief_concern: z.string(),
  key_diagnoses: z.array(
    z.strictObject({
      name: z.string(),
      status: z.enum(["active", "historical", "suspected"]),
      evidence: z.array(EvidenceRefSchema),
    }),
  ),
  recent_media: z.array(
    z.strictObject({
      resource: EvidenceRefSchema,
      kind: z.enum(["imaging", "lab", "pathology", "note"]),
      date: z.string().nullable(),
      finding: z.string(),
    }),
  ),
  flagged_anomalies: z.array(
    z.strictObject({
      description: z.string(),
      severity: AnomalySeveritySchema,
      source: z.enum(["rule", "model"]),
      evidence: z.array(EvidenceRefSchema),
    }),
  ),
  overview: z.string(),
  word_count: z.number().int().max(200),
  confidence: z.strictObject({
    level: ConfidenceLevelSchema,
    score: z.number().min(0).max(1),
    rationale: z.string(),
  }),
  disclaimer: z.string(),
  provider: SummaryProviderSchema,
  model: z.string().nullable(),
  prompt_version: z.string(),
  bundle_hash: z.string(),
  generated_at: z.string(),
  cached: z.boolean(),
  cache_key: z.string(),
  guardrail_notes: z.array(z.string()),
});

export const ResourceDetailSchema = z.strictObject({
  resource: ResourceRefSchema,
  patient: PatientRefSchema,
  text: z.string().nullable(),
  sections: z.array(z.strictObject({ heading: z.string(), body: z.string() })),
  observations: z.array(
    z.strictObject({
      resource_id: z.string(),
      name: z.string(),
      value: z.string(),
      unit: z.string().nullable(),
      interpretation: InterpretationSchema.nullable(),
      reference_range: z.string().nullable(),
    }),
  ),
  issues: z.array(IssueSchema.extend({ path: z.string() })),
  fhir: z.record(z.string(), z.unknown()),
});

/** FHIR Bundle (P2 download): only the envelope is checked here. */
export const BundleSchema = z.looseObject({
  resourceType: z.literal("Bundle"),
  id: z.string(),
  type: z.literal("collection"),
  entry: z.array(z.looseObject({ fullUrl: z.string(), resource: z.looseObject({}) })),
});

export const AuditEntryItemSchema = z.strictObject({
  id: z.number().int(),
  run_id: z.string(),
  record_id: z.string(),
  stage: z.enum(["read", "clean", "identity", "dedupe"]),
  field: z.string().nullable(),
  rule: z.string(),
  before: z.string().nullable(),
  after: z.string().nullable(),
  severity: SeveritySchema,
  message: z.string(),
});

export const SummaryFeedbackRequestSchema = z.strictObject({
  cache_key: z.string(),
  rating: z.enum(["helpful", "not_helpful"]),
  reason: z.enum(["inaccurate", "missing_information", "too_long", "unclear", "other"]).nullable(),
  comment: z.string().max(280).nullable(),
});

export const SummaryFeedbackResponseSchema = z.strictObject({
  id: z.number().int(),
  cache_key: z.string(),
  rating: z.enum(["helpful", "not_helpful"]),
  totals: z.strictObject({ helpful: z.number().int(), not_helpful: z.number().int() }),
});

export type PatientDetail = z.infer<typeof PatientDetailSchema>;
export type PatientResourceItem = z.infer<typeof PatientResourceItemSchema>;
export type PatientResourcesResponse = z.infer<typeof PatientResourcesResponseSchema>;
export type ClinicalSummaryResponse = z.infer<typeof ClinicalSummaryResponseSchema>;
export type ResourceDetail = z.infer<typeof ResourceDetailSchema>;
