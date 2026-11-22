import { SeveritySchema, type Severity } from "@/lib/contract-enums";
import { oneOf, pageSizeParam, positiveInt } from "@/lib/url-params";

export const QUALITY_TABS = ["issues", "audit", "quarantine"] as const;
export type QualityTab = (typeof QUALITY_TABS)[number];

/** URL state of /quality. */
export interface QualityPageParams {
  tab?: QualityTab | undefined;
  severity?: Severity | undefined;
  page?: number | undefined;
  size?: number | undefined;
}

export function parseQualityParams(raw: Record<string, unknown>): QualityPageParams {
  const result: QualityPageParams = {};
  const tab = oneOf(raw.tab, QUALITY_TABS);
  const severity = oneOf(raw.severity, SeveritySchema.options);
  const page = positiveInt(raw.page);
  const size = pageSizeParam(raw.size);
  if (tab) result.tab = tab;
  if (severity) result.severity = severity;
  if (page) result.page = page;
  if (size) result.size = size;
  return result;
}
