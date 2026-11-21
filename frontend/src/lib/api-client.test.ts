import { http, HttpResponse } from "msw";
import { z } from "zod";

import { retryDelay, shouldRetry } from "@/app/queryClient";
import { apiRequest, buildPath } from "@/lib/api-client";
import { ApiError, ContractError, NetworkError } from "@/lib/problem";
import { fixtures } from "@/test/msw/fixtures";
import { problemResponse } from "@/test/msw/handlers";
import { server } from "@/test/msw/server";

const Health = z.strictObject({ status: z.literal("ok"), version: z.string() });

describe("buildPath", () => {
  it("repeats array values and drops empty ones", () => {
    expect(
      buildPath("/search", {
        resource_type: ["DocumentReference", "DiagnosticReport"],
        date_from: "2024-06-01",
        date_to: null,
        mode: undefined,
        q: "",
      }),
    ).toBe(
      "/search?resource_type=DocumentReference&resource_type=DiagnosticReport&date_from=2024-06-01",
    );
    expect(buildPath("/health")).toBe("/health");
  });
});

describe("apiRequest", () => {
  it("parses a valid response", async () => {
    await expect(apiRequest("/health", Health)).resolves.toEqual(fixtures.health);
  });

  it("turns problem+json into ApiError with code, request id and Retry-After", async () => {
    server.use(
      http.post("*/api/search", () =>
        HttpResponse.json(
          { ...fixtures.problem, status: 429, code: "rate_limited" },
          {
            status: 429,
            headers: { "Content-Type": "application/problem+json", "Retry-After": "12" },
          },
        ),
      ),
    );
    const error = await apiRequest("/search", Health, {
      method: "POST",
      body: { query: "x" },
    }).catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    const apiError = error as ApiError;
    expect(apiError.status).toBe(429);
    expect(apiError.code).toBe("rate_limited");
    expect(apiError.requestId).toBe(fixtures.problem.request_id);
    expect(apiError.retryAfterSeconds).toBe(12);
  });

  it("keeps the status when the error body is not a problem", async () => {
    server.use(
      http.get("*/api/health", () => new HttpResponse("<html>Bad gateway</html>", { status: 502 })),
    );
    const error = (await apiRequest("/health", Health).catch((e: unknown) => e)) as ApiError;
    expect(error.status).toBe(502);
    expect(error.problem).toBeNull();
  });

  it("rejects a response that breaks the contract", async () => {
    server.use(http.get("*/api/health", () => HttpResponse.json({ status: "ok" })));
    await expect(apiRequest("/health", Health)).rejects.toBeInstanceOf(ContractError);
  });

  it("wraps network failures", async () => {
    server.use(http.get("*/api/health", () => HttpResponse.error()));
    await expect(apiRequest("/health", Health)).rejects.toBeInstanceOf(NetworkError);
  });

  it("sends JSON bodies", async () => {
    let seen: unknown = null;
    server.use(
      http.post("*/api/search", async ({ request }) => {
        seen = { type: request.headers.get("content-type"), body: await request.json() };
        return problemResponse(503, "search_index_empty");
      }),
    );
    await apiRequest("/search", Health, { method: "POST", body: { query: "chest" } }).catch(
      () => null,
    );
    expect(seen).toEqual({ type: "application/json", body: { query: "chest" } });
  });
});

describe("retry policy (docs/04 section 11.2)", () => {
  const err = (status: number, retry: number | null = null) => new ApiError(status, null, retry);

  it.each([
    [err(422), 0, false],
    [err(404), 0, false],
    [err(429), 0, true],
    [err(429), 1, false],
    [err(503), 1, true],
    [err(500), 2, false],
  ])("%s after %i failures retries: %s", (error, count, expected) => {
    expect(shouldRetry(count, error)).toBe(expected);
  });

  it("retries network failures twice", () => {
    const network: unknown = new NetworkError(null);
    expect(shouldRetry(0, network)).toBe(true);
    expect(shouldRetry(2, network)).toBe(false);
  });

  it("waits Retry-After seconds on 429", () => {
    expect(retryDelay(1, err(429, 12))).toBe(12_000);
    expect(retryDelay(1, err(503))).toBe(1000);
  });
});
