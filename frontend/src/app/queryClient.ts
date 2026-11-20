import { QueryClient } from "@tanstack/react-query";

/** One client per app. Query defaults follow docs/04-API-CONTRACT.md section 11 (Phase 5). */
export function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: { staleTime: 30_000, retry: 1, refetchOnWindowFocus: false },
    },
  });
}
