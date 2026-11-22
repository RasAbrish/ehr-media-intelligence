/** Enums from docs/04-API-CONTRACT.md section 2.1. */
import { z } from "@/lib/zod";

export const ResourceTypeSchema = z.enum([
  "Patient",
  "Encounter",
  "DocumentReference",
  "DiagnosticReport",
  "Observation",
]);
export const SearchableTypeSchema = z.enum([
  "DocumentReference",
  "DiagnosticReport",
  "Observation",
  "ClinicalSummary",
]);
export const GenderSchema = z.enum(["male", "female", "other", "unknown"]);
export const DocTypeSchema = z.enum([
  "discharge_summary",
  "progress_note",
  "consult_note",
  "imaging_report",
  "lab_report",
  "pathology_report",
  "scanned_document",
]);
export const ReportCategorySchema = z.enum(["LAB", "RAD", "PAT"]);
export const SeveritySchema = z.enum(["info", "warning", "error"]);
export const AnomalySeveritySchema = z.enum(["low", "moderate", "high"]);
export const ConfidenceLevelSchema = z.enum(["low", "medium", "high"]);
export const SearchModeSchema = z.enum(["semantic", "hybrid"]);
export const SearchSortSchema = z.enum(["relevance", "newest"]);
export const MatchTypeSchema = z.enum(["semantic", "lexical", "hybrid", "mrn"]);
export const SummaryProviderSchema = z.enum(["anthropic", "extractive"]);
export const PipelineStageSchema = z.enum(["ingest", "normalize", "summarize", "index"]);
export const RunStatusSchema = z.enum(["queued", "running", "succeeded", "failed"]);
export const InterpretationSchema = z.enum(["LL", "L", "N", "H", "HH"]);
export const EvidenceTypeSchema = z.enum([
  "DocumentReference",
  "DiagnosticReport",
  "Observation",
  "Encounter",
]);

export type ResourceType = z.infer<typeof ResourceTypeSchema>;
export type SearchableType = z.infer<typeof SearchableTypeSchema>;
export type Severity = z.infer<typeof SeveritySchema>;
export type AnomalySeverity = z.infer<typeof AnomalySeveritySchema>;
export type ConfidenceLevel = z.infer<typeof ConfidenceLevelSchema>;
export type SearchMode = z.infer<typeof SearchModeSchema>;
export type SearchSort = z.infer<typeof SearchSortSchema>;
export type MatchType = z.infer<typeof MatchTypeSchema>;
export type Interpretation = z.infer<typeof InterpretationSchema>;
