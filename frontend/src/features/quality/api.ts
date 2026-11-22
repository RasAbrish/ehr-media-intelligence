import { keepPreviousData, queryOptions } from "@tanstack/react-query";

import {
  AuditPageSchema,
  QualityOverviewSchema,
  QuarantinePageSchema,
  ValidationPageSchema,
} from "@/features/quality/schemas";
import { apiRequest } from "@/lib/api-client";
import { keys, type PageParams } from "@/lib/query-keys";

const THIRTY_SECONDS = 30_000;

const query = ({ page, size, severity }: PageParams) => ({ page, page_size: size, severity });

export function overviewQuery() {
  return queryOptions({
    queryKey: keys.quality.overview,
    queryFn: ({ signal }) => apiRequest("/quality/overview", QualityOverviewSchema, { signal }),
    staleTime: THIRTY_SECONDS,
  });
}

export function validationQuery(params: PageParams) {
  return queryOptions({
    queryKey: keys.quality.validation(params),
    queryFn: ({ signal }) =>
      apiRequest("/quality/validation", ValidationPageSchema, { query: query(params), signal }),
    staleTime: THIRTY_SECONDS,
    placeholderData: keepPreviousData,
  });
}

export function auditQuery(params: PageParams) {
  return queryOptions({
    queryKey: keys.quality.audit(params),
    queryFn: ({ signal }) =>
      apiRequest("/quality/audit", AuditPageSchema, { query: query(params), signal }),
    staleTime: THIRTY_SECONDS,
    placeholderData: keepPreviousData,
  });
}

export function quarantineQuery(params: PageParams) {
  return queryOptions({
    queryKey: keys.quality.quarantine(params),
    queryFn: ({ signal }) =>
      apiRequest("/quality/quarantine", QuarantinePageSchema, { query: query(params), signal }),
    staleTime: THIRTY_SECONDS,
    placeholderData: keepPreviousData,
  });
}
