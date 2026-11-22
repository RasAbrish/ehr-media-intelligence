import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";

import { copy } from "@/lib/copy";
import { seriousAxeViolations } from "@/test/axe";
import { fixtures } from "@/test/msw/fixtures";
import { pageOf, problemResponse, qualityRows } from "@/test/msw/handlers";
import { server } from "@/test/msw/server";
import { renderApp } from "@/test/render-app";

describe("Data quality page (FR-5.8)", () => {
  it("shows the six KPIs", async () => {
    await renderApp("/quality");
    const strip = within(await screen.findByRole("list", { name: copy.quality.kpiLabel }));
    expect(strip.getAllByRole("listitem")).toHaveLength(6);
    const { kpis } = copy.quality;
    for (const [label, value] of [
      [kpis.ingested, "412"],
      [kpis.duplicates, "18"],
      [kpis.merged, "3"],
      [kpis.conflicts, "2"],
      [kpis.valid, copy.quality.validOf(60, 60)],
      [kpis.issues, "9"],
    ] as const) {
      expect(strip.getByText(label).closest("li")).toHaveTextContent(value);
    }
  });

  it("lists issues and filters them by severity", async () => {
    const user = userEvent.setup();
    const asked: string[] = [];
    server.use(
      http.get("*/api/quality/validation", ({ request }) => {
        asked.push(new URL(request.url).searchParams.get("severity") ?? "all");
        return HttpResponse.json(pageOf([qualityRows.issue]));
      }),
    );
    await renderApp("/quality");
    expect(await screen.findByText(qualityRows.issue.code)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: fixtures.patient.display_name })).toHaveAttribute(
      "href",
      expect.stringContaining("/patients?patient="),
    );
    await user.selectOptions(screen.getByLabelText(copy.quality.severity), "error");
    await waitFor(() => {
      expect(asked).toEqual(["all", "error"]);
    });
  });

  it("switches to the audit log and quarantine through the URL", async () => {
    const user = userEvent.setup();
    const { router } = await renderApp("/quality");
    await user.click(await screen.findByRole("tab", { name: copy.quality.tabs.audit }));
    expect(await screen.findByText("J*** D**")).toBeInTheDocument();
    expect(router.state.location.search).toMatchObject({ tab: "audit" });
    await user.click(screen.getByRole("tab", { name: copy.quality.tabs.quarantine }));
    expect(await screen.findByText(qualityRows.quarantined.source_locator)).toBeInTheDocument();
    expect(screen.queryByLabelText(copy.quality.severity)).toBeNull();
  });

  it("shows the designed empty state", async () => {
    server.use(http.get("*/api/quality/validation", () => HttpResponse.json(pageOf([]))));
    await renderApp("/quality");
    expect(await screen.findByText(copy.quality.noIssuesBody)).toBeInTheDocument();
  });

  it("shows the pipeline hint before the first run", async () => {
    server.use(
      http.get("*/api/quality/overview", () =>
        HttpResponse.json({
          ...fixtures.overview,
          validation: { ...fixtures.overview.validation, bundles: 0, valid_bundles: 0 },
        }),
      ),
    );
    await renderApp("/quality");
    expect(await screen.findByText(copy.indexEmpty.title)).toBeInTheDocument();
  });

  it("names the failure", async () => {
    server.use(http.get("*/api/quality/overview", () => problemResponse(422, "validation_error")));
    await renderApp("/quality");
    expect(await screen.findByText(copy.errors.qualityTitle)).toBeInTheDocument();
  });

  it.each(["issues", "audit", "quarantine"])("has no serious axe violations on %s", async (tab) => {
    const { container } = await renderApp(`/quality?tab=${tab}`);
    await screen.findByRole("table");
    expect(await seriousAxeViolations(container)).toEqual([]);
  });
});
