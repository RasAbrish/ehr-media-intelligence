import { queryOptions } from "@tanstack/react-query";

import { apiRequest } from "@/lib/api-client";
import { keys } from "@/lib/query-keys";
import { ReadyResponseSchema } from "@/lib/system-schemas";

/** /ready answers 503 with the same body when a component is down; the page only needs counts. */
export function readyQuery() {
  return queryOptions({
    queryKey: keys.ready,
    queryFn: ({ signal }) => apiRequest("/ready", ReadyResponseSchema, { signal }),
    staleTime: 30_000,
    retry: false,
  });
}
