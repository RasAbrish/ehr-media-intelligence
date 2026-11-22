import { keepPreviousData, queryOptions } from "@tanstack/react-query";
import type { z } from "zod";

import {
  AuditPageSchema,
  ClinicalSummaryResponseSchema,
  PatientDetailSchema,
  PatientPageSchema,
  PatientResourcesResponseSchema,
  ResourceDetailSchema,
  SummaryFeedbackResponseSchema,
  type SummaryFeedbackRequestSchema,
} from "@/features/patients/schemas";
import { apiRequest } from "@/lib/api-client";
import { clientId } from "@/lib/client-id";
import { keys, type PageParams, type PatientListParams } from "@/lib/query-keys";

const FIVE_MINUTES = 5 * 60_000;

export type FeedbackVote = z.infer<typeof SummaryFeedbackRequestSchema>;

export function sendFeedback(key: string, body: FeedbackVote) {
  return apiRequest(`/patients/${key}/summary/feedback`, SummaryFeedbackResponseSchema, {
    method: "POST",
    body,
    headers: { "X-Client-Id": clientId() },
  });
}

export function directoryQuery(params: PatientListParams) {
  return queryOptions({
    queryKey: keys.patients.list(params),
    queryFn: ({ signal }) =>
      apiRequest("/patients", PatientPageSchema, {
        query: {
          q: params.q,
          sort: params.sort,
          order: params.order,
          page: params.page,
          page_size: params.size,
          conflict_only: params.conflictOnly ? "true" : undefined,
        },
        signal,
      }),
    staleTime: 30_000,
    placeholderData: keepPreviousData,
  });
}

export function patientAuditQuery(key: string, params: PageParams) {
  return queryOptions({
    queryKey: keys.patients.audit(key, params),
    queryFn: ({ signal }) =>
      apiRequest(`/patients/${key}/audit`, AuditPageSchema, {
        query: { page: params.page, page_size: params.size, severity: params.severity },
        signal,
      }),
    staleTime: 30_000,
  });
}

export function patientQuery(key: string) {
  return queryOptions({
    queryKey: keys.patients.detail(key),
    queryFn: ({ signal }) => apiRequest(`/patients/${key}`, PatientDetailSchema, { signal }),
    staleTime: FIVE_MINUTES,
  });
}

export function summaryQuery(key: string) {
  return queryOptions({
    queryKey: keys.patients.summary(key),
    queryFn: ({ signal }) =>
      apiRequest(`/patients/${key}/summary`, ClinicalSummaryResponseSchema, { signal }),
    staleTime: FIVE_MINUTES,
  });
}

export function resourcesQuery(key: string) {
  return queryOptions({
    queryKey: keys.patients.resources(key),
    queryFn: ({ signal }) =>
      apiRequest(`/patients/${key}/resources`, PatientResourcesResponseSchema, { signal }),
    staleTime: FIVE_MINUTES,
  });
}

export function resourceQuery(type: string, id: string) {
  return queryOptions({
    queryKey: keys.resource(type, id),
    queryFn: ({ signal }) =>
      apiRequest(`/resources/${type}/${id}`, ResourceDetailSchema, { signal }),
    staleTime: 10 * 60_000,
  });
}
