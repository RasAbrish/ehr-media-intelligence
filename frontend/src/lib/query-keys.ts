/** Query key factory (docs/04 section 11.1). */
import type { SearchableType, SearchMode } from "@/lib/contract-enums";

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

export const keys = {
  ready: ["ready"] as const,
  search: (params: SearchParams) => ["search", params] as const,
  patients: {
    all: ["patients"] as const,
    detail: (key: string) => ["patients", key] as const,
    resources: (key: string, params: ResourceListParams = {}) =>
      ["patients", key, "resources", params] as const,
    summary: (key: string) => ["patients", key, "summary"] as const,
  },
  resource: (type: string, id: string) => ["resource", type, id] as const,
};
