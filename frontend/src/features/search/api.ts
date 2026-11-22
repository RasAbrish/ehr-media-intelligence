import { keepPreviousData, queryOptions } from "@tanstack/react-query";

import { SearchResponseSchema } from "@/features/search/schemas";
import { apiRequest } from "@/lib/api-client";
import { QUERY_MIN } from "@/features/search/schemas";
import { keys, type SearchParams } from "@/lib/query-keys";

export function searchQuery(params: SearchParams) {
  return queryOptions({
    queryKey: keys.search(params),
    queryFn: ({ signal }) =>
      apiRequest("/search", SearchResponseSchema, {
        method: "POST",
        body: { query: params.q },
        query: {
          resource_type: params.types,
          date_from: params.from,
          date_to: params.to,
          mode: params.mode,
          sort: params.sort,
        },
        signal,
      }),
    enabled: params.q.trim().length >= QUERY_MIN,
    staleTime: 60_000,
    placeholderData: keepPreviousData,
  });
}
