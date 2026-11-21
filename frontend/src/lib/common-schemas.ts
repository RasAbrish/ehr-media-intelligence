/** Shared objects from docs/04 section 2.2. Optional fields are present as null, never omitted. */
import { z } from "zod";

import {
  DocTypeSchema,
  EvidenceTypeSchema,
  GenderSchema,
  ReportCategorySchema,
  SearchableTypeSchema,
} from "@/lib/contract-enums";

export const PatientRefSchema = z.strictObject({
  patient_key: z.string(),
  display_name: z.string(),
  mrn: z.string(),
  birth_date: z.string().nullable(),
  age: z.number().int().nullable(),
  gender: GenderSchema,
  identity_conflict: z.boolean(),
});

export const ResourceRefSchema = z.strictObject({
  resource_type: z.union([SearchableTypeSchema, z.literal("Encounter")]),
  resource_id: z.string(),
  date: z.string().nullable(),
  title: z.string(),
  subtype: z.union([DocTypeSchema, ReportCategorySchema]).nullable(),
  is_valid: z.boolean(),
});

export const EvidenceRefSchema = z.strictObject({
  resource_type: EvidenceTypeSchema,
  resource_id: z.string(),
});

export function pageSchema<T extends z.ZodType>(item: T) {
  return z.strictObject({
    items: z.array(item),
    page: z.number().int(),
    page_size: z.number().int(),
    total: z.number().int(),
    total_pages: z.number().int(),
  });
}

export type PatientRef = z.infer<typeof PatientRefSchema>;
export type ResourceRef = z.infer<typeof ResourceRefSchema>;
export type EvidenceRef = z.infer<typeof EvidenceRefSchema>;
