import { queryOptions } from "@tanstack/react-query";

import {
  ClinicalSummaryResponseSchema,
  PatientDetailSchema,
  PatientResourcesResponseSchema,
  ResourceDetailSchema,
} from "@/features/patients/schemas";
import { apiRequest } from "@/lib/api-client";
import { keys } from "@/lib/query-keys";

const FIVE_MINUTES = 5 * 60_000;

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
