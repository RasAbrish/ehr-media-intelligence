/** Query key factory (docs/04 section 11.1). */
import type { SearchableType, SearchMode, Severity } from "@/lib/contract-enums";

export interface SearchParams {
  q: string;
  types: SearchableType[];
  from: string | null;
  to: string | null;
  mode?: SearchMode;
}

export interface ResourceListParams {
  sort?: "date" | "type" | "title";
  order?: "asc" | "desc";
}

export interface PatientListParams {
  q: string;
  sort: "name" | "mrn" | "birth_date" | "last_activity" | "resource_count";
  order: "asc" | "desc";
  page: number;
  size: number;
  conflictOnly: boolean;
}

export interface PageParams {
  page: number;
  size: number;
  severity?: Severity | undefined;
}

export const keys = {
  stats: ["stats"] as const,
  quality: {
    overview: ["quality", "overview"] as const,
    validation: (params: PageParams) => ["quality", "validation", params] as const,
    audit: (params: PageParams) => ["quality", "audit", params] as const,
    quarantine: (params: PageParams) => ["quality", "quarantine", params] as const,
  },
  ready: ["ready"] as const,
  search: (params: SearchParams) => ["search", params] as const,
  patients: {
    all: ["patients"] as const,
    list: (params: PatientListParams) => ["patients", "list", params] as const,
    audit: (key: string, params: PageParams) => ["patients", key, "audit", params] as const,
    detail: (key: string) => ["patients", key] as const,
    resources: (key: string, params: ResourceListParams = {}) =>
      ["patients", key, "resources", params] as const,
    summary: (key: string) => ["patients", key, "summary"] as const,
  },
  resource: (type: string, id: string) => ["resource", type, id] as const,
};
