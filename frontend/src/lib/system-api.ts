import { queryOptions } from "@tanstack/react-query";

import { apiRequest } from "@/lib/api-client";
import { keys } from "@/lib/query-keys";
import {
  HealthResponseSchema,
  ReadyResponseSchema,
  StatsResponseSchema,
} from "@/lib/system-schemas";

/** /ready answers 503 with the same body when a component is down; the page only needs counts. */
export function readyQuery() {
  return queryOptions({
    queryKey: keys.ready,
    queryFn: ({ signal }) => apiRequest("/ready", ReadyResponseSchema, { signal }),
    staleTime: 30_000,
    retry: false,
  });
}

export function statsQuery() {
  return queryOptions({
    queryKey: keys.stats,
    queryFn: ({ signal }) => apiRequest("/stats", StatsResponseSchema, { signal }),
    staleTime: 30_000,
  });
}

/** Liveness only: used to notice when a sleeping host has woken. */
export function healthQuery() {
  return queryOptions({
    queryKey: keys.health,
    queryFn: ({ signal }) => apiRequest("/health", HealthResponseSchema, { signal }),
    retry: false,
  });
}
