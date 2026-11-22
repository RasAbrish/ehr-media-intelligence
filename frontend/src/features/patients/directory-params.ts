import { oneOf, pageSizeParam, patientParam, positiveInt, textParam } from "@/lib/url-params";

export const DIRECTORY_SORTS = [
  "name",
  "mrn",
  "birth_date",
  "last_activity",
  "resource_count",
] as const;
export type DirectorySort = (typeof DIRECTORY_SORTS)[number];

/** URL state of /patients. */
export interface DirectoryPageParams {
  q?: string | undefined;
  sort?: DirectorySort | undefined;
  order?: "asc" | "desc" | undefined;
  page?: number | undefined;
  size?: number | undefined;
  conflict?: true | undefined;
  patient?: string | undefined;
}

export function parseDirectoryParams(raw: Record<string, unknown>): DirectoryPageParams {
  const result: DirectoryPageParams = {};
  const q = textParam(raw.q, 100);
  const sort = oneOf(raw.sort, DIRECTORY_SORTS);
  const order = oneOf(raw.order, ["asc", "desc"] as const);
  const page = positiveInt(raw.page);
  const size = pageSizeParam(raw.size);
  const patient = patientParam(raw.patient);
  if (q) result.q = q;
  if (sort) result.sort = sort;
  if (order) result.order = order;
  if (page) result.page = page;
  if (size) result.size = size;
  if (raw.conflict === true || raw.conflict === "true") result.conflict = true;
  if (patient) result.patient = patient;
  return result;
}
