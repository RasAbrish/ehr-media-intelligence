import { QueryClient } from "@tanstack/react-query";

import { ApiError } from "@/lib/problem";

const MAX_SERVER_RETRIES = 2;

/** docs/04 section 11.2: 4xx never retry, 429 once after Retry-After, 5xx and network twice. */
export function shouldRetry(failureCount: number, error: unknown): boolean {
  if (error instanceof ApiError) {
    if (error.status === 429) return failureCount < 1;
    if (error.status < 500) return false;
  }
  return failureCount < MAX_SERVER_RETRIES;
}

export function retryDelay(failureCount: number, error: unknown): number {
  if (error instanceof ApiError && error.status === 429 && error.retryAfterSeconds !== null) {
    return error.retryAfterSeconds * 1000;
  }
  return Math.min(500 * 2 ** failureCount, 4000);
}

/** One client per app; per-query staleTime is set by each hook. */
export function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: { staleTime: 30_000, retry: shouldRetry, retryDelay, refetchOnWindowFocus: false },
    },
  });
}
