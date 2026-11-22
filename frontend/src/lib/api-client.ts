/**
 * Typed fetch for the API (docs/04). The browser calls `/api/*`, which the Vite dev
 * server and nginx proxy to the backend. Every response is checked against its Zod
 * schema; errors become `ApiError` (with the RFC 9457 problem), `NetworkError` or
 * `ContractError`.
 */
import type { z } from "zod";

import { ApiError, ContractError, NetworkError, ProblemSchema } from "@/lib/problem";

export const API_BASE = "/api";

type QueryValue = string | number | readonly string[] | null | undefined;

export interface RequestOptions {
  method?: "GET" | "POST";
  query?: Record<string, QueryValue>;
  body?: unknown;
  headers?: Record<string, string>;
  signal?: AbortSignal;
  /** The response has no body (204). */
  empty?: boolean;
}

export function buildPath(path: string, query: Record<string, QueryValue> = {}): string {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value === null || value === undefined || value === "") continue;
    if (Array.isArray(value)) {
      for (const item of value as readonly string[]) params.append(key, item);
    } else {
      params.append(key, String(value));
    }
  }
  const search = params.toString();
  return search ? `${path}?${search}` : path;
}

function retryAfter(response: Response): number | null {
  const header = response.headers.get("Retry-After");
  if (!header) return null;
  const seconds = Number(header);
  return Number.isFinite(seconds) && seconds >= 0 ? seconds : null;
}

async function toApiError(response: Response): Promise<ApiError> {
  let problem = null;
  try {
    const parsed = ProblemSchema.safeParse(await response.json());
    if (parsed.success) problem = parsed.data;
  } catch {
    // Not JSON (a proxy error page, for example): keep the status only.
  }
  return new ApiError(response.status, problem, retryAfter(response));
}

export async function apiRequest<S extends z.ZodType>(
  path: string,
  schema: S,
  options: RequestOptions = {},
): Promise<z.infer<S>> {
  const url = API_BASE + buildPath(path, options.query);
  const init: RequestInit = {
    method: options.method ?? "GET",
    headers: {
      Accept: "application/json",
      // CSRF check: every POST needs it (docs/04 section 3a).
      "X-Requested-With": "ehr-mip",
      ...(options.body === undefined ? {} : { "Content-Type": "application/json" }),
      ...options.headers,
    },
  };
  if (options.body !== undefined) init.body = JSON.stringify(options.body);
  if (options.signal) init.signal = options.signal;
  let response: Response;
  try {
    response = await fetch(url, init);
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") throw error;
    throw new NetworkError(error);
  }
  if (!response.ok) throw await toApiError(response);
  if (options.empty) return schema.parse(undefined);
  const parsed = schema.safeParse(await response.json());
  if (!parsed.success) throw new ContractError(path, parsed.error);
  return parsed.data;
}
