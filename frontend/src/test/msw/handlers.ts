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

export function pageOf<T>(items: T[]) {
  return { items, page: 1, page_size: 50, total: items.length, total_pages: 1 };
}

const { patient_key, display_name, mrn, birth_date, age, gender, identity_conflict } =
  fixtures.patient;
/** docs/04 sections 8.2 to 8.4 define these shapes without an example. */
export const qualityRows = {
  issue: {
    id: 1,
    patient: { patient_key, display_name, mrn, birth_date, age, gender, identity_conflict },
    resource_type: "Patient",
    resource_id: patient_key,
    path: "Patient.birthDate",
    severity: "warning",
    code: "patient.birthdate_missing",
    message: "Birth date is missing.",
  },
  audit: {
    ...fixtures.auditEntry,
    field: "name",
    before: "D**, J***",
    after: "J*** D**",
    patient: null,
  },
  quarantined: {
    id: 16,
    run_id: "run-1",
    source_locator: "notes/note_082_scan.txt",
    reason: "empty_document",
    payload_preview: "{}",
  },
};

export const handlers = [
  http.get("*/api/stats", () => HttpResponse.json(fixtures.stats)),
  http.get("*/api/patients", () => HttpResponse.json(fixtures.directory)),
  http.get("*/api/patients/:key/audit", () => HttpResponse.json(pageOf([fixtures.auditEntry]))),
  http.get("*/api/quality/overview", () => HttpResponse.json(fixtures.overview)),
  http.get("*/api/quality/validation", () => HttpResponse.json(pageOf([qualityRows.issue]))),
  http.get("*/api/quality/audit", () => HttpResponse.json(pageOf([qualityRows.audit]))),
  http.get("*/api/quality/quarantine", () => HttpResponse.json(pageOf([qualityRows.quarantined]))),
  http.get("*/api/health", () => HttpResponse.json(fixtures.health)),
  http.get("*/api/ready", () => HttpResponse.json(fixtures.ready)),
  http.post("*/api/search", async ({ request }) => {
    const body = (await request.json()) as { query: string };
    return HttpResponse.json({ ...fixtures.search, query: body.query });
  }),
  http.get("*/api/patients/:key/summary", () => HttpResponse.json(fixtures.summary)),
  http.get("*/api/patients/:key/resources", () => HttpResponse.json(fixtures.resources)),
  http.get("*/api/patients/:key", () => HttpResponse.json(fixtures.patient)),
  http.post("*/api/patients/:key/summary/feedback", () =>
    HttpResponse.json(fixtures.feedback, { status: 201 }),
  ),
  http.get("*/api/resources/:type/:id", () => HttpResponse.json(fixtures.resource)),
];
