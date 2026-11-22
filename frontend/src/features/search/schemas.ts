/** POST /search (docs/04 section 5.1). */
import { z } from "@/lib/zod";

import { PatientRefSchema, ResourceRefSchema } from "@/lib/common-schemas";
import {
  MatchTypeSchema,
  SearchableTypeSchema,
  SearchModeSchema,
  SearchSortSchema,
} from "@/lib/contract-enums";

export const QUERY_MIN = 2;
export const QUERY_MAX = 500;

export const SearchRequestSchema = z.strictObject({
  query: z.string().trim().min(QUERY_MIN).max(QUERY_MAX),
});

export const SearchResultSchema = z.strictObject({
  rank: z.number().int(),
  score: z.number(),
  semantic_score: z.number(),
  match_type: MatchTypeSchema,
  patient: PatientRefSchema,
  resource: ResourceRefSchema,
  snippet: z.string(),
  highlights: z.array(z.tuple([z.number().int(), z.number().int()])),
  summary_snippet: z.string().nullable(),
});

export const SearchResponseSchema = z.strictObject({
  query: z.string(),
  took_ms: z.number(),
  total: z.number().int(),
  mode: SearchModeSchema,
  sort: SearchSortSchema,
  filters: z.strictObject({
    resource_type: z.array(SearchableTypeSchema),
    date_from: z.string().nullable(),
    date_to: z.string().nullable(),
    patient_key: z.string().nullable(),
  }),
  results: z.array(SearchResultSchema),
});

export type SearchResult = z.infer<typeof SearchResultSchema>;
export type SearchResponse = z.infer<typeof SearchResponseSchema>;
