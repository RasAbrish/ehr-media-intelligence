import { MutationCache, QueryCache, QueryClient } from "@tanstack/react-query";

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

/** A 401 `not_authenticated` anywhere means the session ended (docs/04 section 3a). */
export function isSignedOutError(error: unknown): boolean {
  return (
    error instanceof ApiError &&
    error.status === 401 &&
    error.problem?.code !== "invalid_credentials"
  );
}

/** One client per app; per-query staleTime is set by each hook. */
export function createQueryClient(onSignedOut: () => void = () => undefined): QueryClient {
  const onError = (error: unknown) => {
    if (isSignedOutError(error)) onSignedOut();
  };
  return new QueryClient({
    queryCache: new QueryCache({ onError }),
    mutationCache: new MutationCache({ onError }),
    defaultOptions: {
      queries: { staleTime: 30_000, retry: shouldRetry, retryDelay, refetchOnWindowFocus: false },
    },
  });
}
