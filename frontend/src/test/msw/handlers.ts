/**
 * MSW handlers built from the docs/04 examples, shared by component tests and Storybook.
 * Tests override single routes with `server.use(...)` for error and empty states.
 */
import { http, HttpResponse } from "msw";

import { fixtures } from "@/test/msw/fixtures";

export const PROBLEM = { "Content-Type": "application/problem+json" };

export function problemResponse(status: number, code: string, detail = "Request failed") {
  return HttpResponse.json(
    {
      ...fixtures.problem,
      status,
      code,
      detail,
      type: `https://ehr-mip.local/problems/${code}`,
      errors: [],
    },
    { status, headers: PROBLEM },
  );
}

export const handlers = [
  http.get("*/api/health", () => HttpResponse.json(fixtures.health)),
  http.get("*/api/ready", () => HttpResponse.json(fixtures.ready)),
  http.post("*/api/search", async ({ request }) => {
    const body = (await request.json()) as { query: string };
    return HttpResponse.json({ ...fixtures.search, query: body.query });
  }),
  http.get("*/api/patients/:key/summary", () => HttpResponse.json(fixtures.summary)),
  http.get("*/api/patients/:key/resources", () => HttpResponse.json(fixtures.resources)),
  http.get("*/api/patients/:key", () => HttpResponse.json(fixtures.patient)),
  http.get("*/api/resources/:type/:id", () => HttpResponse.json(fixtures.resource)),
];
