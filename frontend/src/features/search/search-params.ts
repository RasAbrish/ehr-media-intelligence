/**
 * URL state of the search page: `?q=&type=&from=&to=&patient=` (docs/06 sections 8.1, 13).
 * Parsing is forgiving: an invalid value is dropped instead of breaking the page, and an
 * inverted range keeps only the start date.
 */
import { z } from "@/lib/zod";

import { SearchableTypeSchema, type SearchableType } from "@/lib/contract-enums";
import { patientParam, textParam } from "@/lib/url-params";

const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/;

export interface SearchPageParams {
  q?: string;
  type?: SearchableType[];
  from?: string;
  to?: string;
  /** Relevance is the default and never in the URL. */
  sort?: "newest";
  patient?: string;
}

function isRealDate(value: string): boolean {
  if (!ISO_DATE.test(value)) return false;
  const parsed = new Date(`${value}T00:00:00Z`);
  return !Number.isNaN(parsed.getTime()) && parsed.toISOString().startsWith(value);
}

const DateParam = z.string().refine(isRealDate);

/** Zod check used by the filter bar before it changes the URL. */
export const DateRangeSchema = z
  .object({ from: DateParam.nullable(), to: DateParam.nullable() })
  .refine((r) => !r.from || !r.to || r.from <= r.to, { message: "range", path: ["to"] });

export function parseSearchParams(raw: Record<string, unknown>): SearchPageParams {
  const result: SearchPageParams = {};
  const q = textParam(raw.q);
  if (q) result.q = q;
  const types = Array.isArray(raw.type) ? raw.type : raw.type ? [raw.type] : [];
  const valid = types.filter((t): t is SearchableType => SearchableTypeSchema.safeParse(t).success);
  if (valid.length) result.type = [...new Set(valid)];
  const from = typeof raw.from === "string" && isRealDate(raw.from) ? raw.from : undefined;
  const to = typeof raw.to === "string" && isRealDate(raw.to) ? raw.to : undefined;
  if (from) result.from = from;
  if (to && (!from || from <= to)) result.to = to;
  if (raw.sort === "newest") result.sort = "newest";
  const patient = patientParam(raw.patient);
  if (patient) result.patient = patient;
  return result;
}
