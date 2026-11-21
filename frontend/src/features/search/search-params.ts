/**
 * URL state of the search page: `?q=&type=&from=&to=&patient=` (docs/06 sections 8.1, 13).
 * Parsing is forgiving: an invalid value is dropped instead of breaking the page, and an
 * inverted range keeps only the start date.
 */
import { z } from "zod";

import { SearchableTypeSchema, type SearchableType } from "@/lib/contract-enums";

const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/;

export interface SearchPageParams {
  q?: string;
  type?: SearchableType[];
  from?: string;
  to?: string;
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
  if (typeof raw.q === "string" && raw.q.trim()) result.q = raw.q.slice(0, 500);
  const types = Array.isArray(raw.type) ? raw.type : raw.type ? [raw.type] : [];
  const valid = types.filter((t): t is SearchableType => SearchableTypeSchema.safeParse(t).success);
  if (valid.length) result.type = [...new Set(valid)];
  const from = typeof raw.from === "string" && isRealDate(raw.from) ? raw.from : undefined;
  const to = typeof raw.to === "string" && isRealDate(raw.to) ? raw.to : undefined;
  if (from) result.from = from;
  if (to && (!from || from <= to)) result.to = to;
  if (typeof raw.patient === "string" && /^[0-9a-f-]{8,64}$/i.test(raw.patient)) {
    result.patient = raw.patient;
  }
  return result;
}
