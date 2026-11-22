import { queryOptions } from "@tanstack/react-query";

import { CurrentUserSchema, type LoginRequest } from "@/features/auth/schemas";
import { apiRequest } from "@/lib/api-client";
import { z } from "@/lib/zod";
import { keys } from "@/lib/query-keys";

/** The signed-in user. A 401 means signed out; it is never retried. */
export function meQuery() {
  return queryOptions({
    queryKey: keys.me,
    queryFn: ({ signal }) => apiRequest("/auth/me", CurrentUserSchema, { signal }),
    staleTime: 5 * 60_000,
    retry: (failures, error) =>
      !(error instanceof Error && "status" in error && error.status === 401) && failures < 2,
  });
}

export function signIn(body: LoginRequest) {
  return apiRequest("/auth/login", CurrentUserSchema, { method: "POST", body });
}

export function signOut() {
  return apiRequest("/auth/logout", z.unknown(), { method: "POST", empty: true });
}

/** Only a same-site path is a safe place to return to after sign-in. */
export function safeNext(value: unknown): string {
  return typeof value === "string" && /^\/(?![/\\])/.test(value) ? value : "/";
}
