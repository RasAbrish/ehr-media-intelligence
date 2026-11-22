import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { delay, http, HttpResponse } from "msw";

import { copy } from "@/lib/copy";
import { seriousAxeViolations } from "@/test/axe";
import { must } from "@/test/must";
import { fixtures } from "@/test/msw/fixtures";
import { problemResponse } from "@/test/msw/handlers";
import { server } from "@/test/msw/server";
import { renderApp } from "@/test/render-app";

const KEY = fixtures.patient.patient_key;

async function openDrawer(path = `/?patient=${KEY}`) {
  const view = await renderApp(path);
  const drawer = await screen.findByRole("dialog", { name: fixtures.patient.display_name });
  return { ...view, drawer };
}

describe("Patient drawer (FR-5.3)", () => {
  it("shows the patient header with MRN, merged MRN, age, sex and date of birth", async () => {
    const { drawer } = await openDrawer();
    expect(within(drawer).getByText(copy.card.mrn("00012345"))).toBeInTheDocument();
    expect(within(drawer).getByText(copy.drawer.alsoKnown("00098765"))).toBeInTheDocument();
    expect(within(drawer).getByText(copy.drawer.mergedTitle(2))).toBeInTheDocument();
    expect(within(drawer).getByText(copy.drawer.born("Mar 14, 1968"))).toBeInTheDocument();
    expect(within(drawer).getByText("57 F")).toBeInTheDocument();
  });

  it("puts the disclaimer first and labels the AI summary (FR-8.2)", async () => {
    const { drawer } = await openDrawer();
    const panel = within(drawer).getByRole("tabpanel");
    const note = await within(panel).findByRole("note");
    expect(note).toHaveTextContent(fixtures.summary.disclaimer);
    expect(panel.firstElementChild?.firstElementChild).toBe(note);
    expect(within(panel).getByText(copy.ai.summaryLabel)).toBeInTheDocument();
    expect(within(panel).getByText(fixtures.summary.model ?? "")).toBeInTheDocument();
    expect(within(panel).getByText(copy.ai.cached)).toBeInTheDocument();
    for (const title of Object.values(copy.ai.sections)) {
      expect(within(panel).getByRole("heading", { name: title })).toBeInTheDocument();
    }
    expect(within(panel).getByText(fixtures.summary.chief_concern)).toBeInTheDocument();
    expect(
      within(panel).getByRole("img", { name: copy.ai.confidenceAria("Medium", "0.65") }),
    ).toBeInTheDocument();
    expect(within(panel).getByText(fixtures.summary.confidence.rationale)).toBeInTheDocument();
  });

  it("marks data quality anomalies, suspected diagnoses and offline summaries", async () => {
    const user = userEvent.setup();
    server.use(
      http.get("*/api/patients/:key/summary", () =>
        HttpResponse.json({
          ...fixtures.summary,
          provider: "extractive",
          model: null,
          chief_concern: "Not documented",
          guardrail_notes: ["fallback_extractive (refusal)"],
          key_diagnoses: [{ ...fixtures.summary.key_diagnoses[0], status: "suspected" }],
        }),
      ),
    );
    const { drawer } = await openDrawer();
    expect(await within(drawer).findByText(copy.ai.offline)).toBeInTheDocument();
    expect(within(drawer).getByText(copy.ai.fallbackNotice)).toBeInTheDocument();
    expect(within(drawer).getAllByText(copy.ai.notDocumented).length).toBeGreaterThan(0);
    expect(within(drawer).getByText(`${copy.ai.severity.low} · ${copy.ai.dq}`)).toBeInTheDocument();
    await user.hover(within(drawer).getByText(copy.ai.suspected));
    expect(await screen.findByText(copy.ai.suspectedHint)).toBeInTheDocument();
  });

  it("evidence chips open the Records tab on the cited row", async () => {
    const user = userEvent.setup();
    const { drawer } = await openDrawer();
    const chip = await within(drawer).findByRole("button", {
      name: "Open source: Discharge Summary · Feb 4, 2025",
    });
    await user.click(chip);
    expect(within(drawer).getByRole("tab", { name: copy.drawer.tabs.records(2) })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    // The Records table is a lazy chunk.
    const row = (
      await within(drawer).findByRole("button", { name: copy.records.open("Discharge Summary") })
    ).closest("tr");
    expect(row).toHaveAttribute("data-highlighted");
  });

  it("lists records with sorting and filters, and opens a record dialog", async () => {
    const user = userEvent.setup();
    const { drawer } = await openDrawer();
    await user.click(within(drawer).getByRole("tab", { name: /^Records/ }));
    const table = await within(drawer).findByRole("table", { name: copy.records.label });
    const titles = () =>
      within(table)
        .getAllByRole("button", { name: /^Open / })
        .map((b) => b.textContent);
    expect(titles()).toEqual(["Discharge Summary", "Potassium"]); // newest first
    await user.click(
      within(table).getByRole("button", { name: copy.records.sortBy(copy.records.columns.title) }),
    );
    expect(within(table).getAllByRole("columnheader")[2]).toHaveAttribute("aria-sort", "ascending");
    expect(titles()).toEqual(["Discharge Summary", "Potassium"]);
    await user.type(within(drawer).getByLabelText(copy.records.filterLabel), "potass");
    expect(titles()).toEqual(["Potassium"]);
    await user.selectOptions(
      within(drawer).getByLabelText(copy.records.typeFilter),
      "DocumentReference",
    );
    expect(within(table).getByText(copy.records.noMatch)).toBeInTheDocument();
    await user.clear(within(drawer).getByLabelText(copy.records.filterLabel));
    await user.click(
      within(table).getByRole("button", { name: copy.records.open("Discharge Summary") }),
    );
    const dialog = await screen.findByRole("dialog", { name: fixtures.resource.resource.title });
    expect(within(dialog).getByRole("heading", { name: "IMPRESSION" })).toBeInTheDocument();
    await user.click(within(dialog).getByRole("tab", { name: copy.dialog.fhir }));
    expect(within(dialog).getByText(/"resourceType": "DocumentReference"/)).toBeInTheDocument();
  });

  it("switches tabs with [ and ]", async () => {
    const user = userEvent.setup();
    const { drawer } = await openDrawer();
    await within(drawer).findByRole("note");
    await user.keyboard("]");
    expect(within(drawer).getByRole("tab", { name: /^Records/ })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    await user.keyboard("[[");
    expect(within(drawer).getByRole("tab", { name: copy.drawer.tabs.summary })).toHaveAttribute(
      "aria-selected",
      "true",
    );
  });

  it("keeps focus inside the drawer when / is pressed", async () => {
    const user = userEvent.setup();
    const { drawer } = await openDrawer();
    const tab = within(drawer).getByRole("tab", { name: copy.drawer.tabs.summary });
    tab.focus();
    await user.keyboard("/");
    expect(tab).toHaveFocus();
  });

  it("does not switch tabs under an open record dialog", async () => {
    const user = userEvent.setup();
    const { drawer } = await openDrawer();
    await user.click(within(drawer).getByRole("tab", { name: /^Records/ }));
    await user.click(
      await within(drawer).findByRole("button", { name: copy.records.open("Potassium") }),
    );
    await screen.findByRole("dialog", { name: fixtures.resource.resource.title });
    await user.keyboard("[[");
    expect(within(drawer).getByRole("tab", { name: /^Records/, hidden: true })).toHaveAttribute(
      "aria-selected",
      "true",
    );
  });

  it("keeps the records filter after the evidence highlight fades", async () => {
    const user = userEvent.setup();
    const { drawer } = await openDrawer();
    await user.click(
      await within(drawer).findByRole("button", {
        name: "Open source: Discharge Summary · Feb 4, 2025",
      }),
    );
    const filter = within(drawer).getByLabelText(copy.records.filterLabel);
    await user.type(filter, "disch");
    await new Promise((resolve) => setTimeout(resolve, 1400));
    expect(within(drawer).getByLabelText(copy.records.filterLabel)).toHaveValue("disch");
  });

  it("keeps undated records last when sorting by date in either direction", async () => {
    const user = userEvent.setup();
    const undated = {
      ...fixtures.resources.items[1],
      resource_id: "undated-1",
      title: "Undated note",
      date: null,
    };
    server.use(
      http.get("*/api/patients/:key/resources", () =>
        HttpResponse.json({
          ...fixtures.resources,
          total: 3,
          items: [...fixtures.resources.items, undated],
        }),
      ),
    );
    const { drawer } = await openDrawer();
    await user.click(within(drawer).getByRole("tab", { name: /^Records/ }));
    const table = await within(drawer).findByRole("table", { name: copy.records.label });
    const titles = () =>
      within(table)
        .getAllByRole("button", { name: /^Open / })
        .map((b) => b.textContent);
    expect(titles().at(-1)).toBe("Undated note");
    await user.click(
      within(table).getByRole("button", { name: copy.records.sortBy(copy.records.columns.date) }),
    );
    expect(titles().at(-1)).toBe("Undated note");
  });

  it("shows not found for an unknown patient", async () => {
    server.use(http.get("*/api/patients/:key", () => problemResponse(404, "patient_not_found")));
    await renderApp(`/?patient=${KEY}`);
    expect(await screen.findByText(copy.drawer.notFoundBody)).toBeInTheDocument();
  });

  it("names the part that failed to load", async () => {
    server.use(
      http.get("*/api/patients/:key/summary", () => problemResponse(500, "internal_error")),
    );
    const { drawer } = await openDrawer();
    expect(
      await within(drawer).findByText(copy.errors.summaryTitle, {}, { timeout: 4000 }),
    ).toBeInTheDocument();
    expect(within(drawer).queryByText(copy.errors.title)).toBeNull();
  });

  it.each([
    ["budget_exceeded", copy.ai.fallbackReasons.budget_exceeded],
    ["refusal", copy.ai.fallbackReasons.refusal],
    ["provider_error", copy.ai.fallbackReasons.provider_error],
  ])("shows the %s fallback reason in the provenance", async (reason, text) => {
    server.use(
      http.get("*/api/patients/:key/summary", () =>
        HttpResponse.json({
          ...fixtures.summary,
          provider: "extractive",
          model: null,
          guardrail_notes: [`fallback_extractive (${reason})`],
        }),
      ),
    );
    const { drawer } = await openDrawer();
    expect(await within(drawer).findByText(text)).toBeInTheDocument();
  });

  it("has a data quality tab with the patient's audit entries", async () => {
    const user = userEvent.setup();
    const asked: string[] = [];
    server.use(
      http.get("*/api/patients/:key/audit", ({ request }) => {
        asked.push(new URL(request.url).searchParams.get("severity") ?? "all");
        return HttpResponse.json({
          items: [fixtures.auditEntry],
          page: 1,
          page_size: 50,
          total: 1,
          total_pages: 1,
        });
      }),
    );
    const { drawer } = await openDrawer();
    await user.click(within(drawer).getByRole("tab", { name: copy.drawer.tabs.quality }));
    expect(await within(drawer).findByText(fixtures.auditEntry.message)).toBeInTheDocument();
    expect(within(drawer).getByText(fixtures.auditEntry.rule)).toBeInTheDocument();
    await user.selectOptions(within(drawer).getByLabelText(copy.quality.severity), "warning");
    await waitFor(() => {
      expect(asked).toEqual(["all", "warning"]);
    });
    expect(await seriousAxeViolations(document.body)).toEqual([]);
  });

  it("says in visible text that the summary is loading (gap 6)", async () => {
    server.use(
      http.get("*/api/patients/:key/summary", async () => {
        await delay(300);
        return HttpResponse.json(fixtures.summary);
      }),
    );
    const { drawer } = await openDrawer();
    const text = within(drawer).getByText(copy.ai.generating);
    expect(text.closest("[aria-busy]")).toHaveAttribute("aria-busy", "true");
  });

  it.each([
    ["patient", "*/api/patients/:key", copy.errors.patientTitle],
    ["records", "*/api/patients/:key/resources", copy.errors.recordsTitle],
  ])("names a %s failure, never 'Search failed' (gap 3)", async (part, path, title) => {
    const user = userEvent.setup();
    server.use(http.get(path, () => problemResponse(500, "internal_error")));
    await renderApp(`/?patient=${KEY}`);
    if (part === "records") await user.click(await screen.findByRole("tab", { name: /^Records/ }));
    expect(await screen.findByText(title, {}, { timeout: 4000 })).toBeInTheDocument();
    expect(screen.queryByText(copy.errors.title)).toBeNull();
  });

  it("shows every citation of an anomaly (gap 12)", async () => {
    const evidence = ["one", "two", "three", "four"].map((id) => ({
      resource_type: "Observation",
      resource_id: `cited-${id}`,
    }));
    server.use(
      http.get("*/api/patients/:key/summary", () =>
        HttpResponse.json({
          ...fixtures.summary,
          key_diagnoses: [],
          recent_media: [],
          flagged_anomalies: [{ ...fixtures.summary.flagged_anomalies[0], evidence }],
        }),
      ),
    );
    const { drawer } = await openDrawer();
    expect(await within(drawer).findAllByRole("button", { name: /^Open source:/ })).toHaveLength(4);
  });

  it("shows the missing-summary state", async () => {
    server.use(
      http.get("*/api/patients/:key/summary", () => problemResponse(404, "summary_not_found")),
    );
    const { drawer } = await openDrawer();
    expect(await within(drawer).findByText(copy.ai.missingBody)).toBeInTheDocument();
  });

  it("closes with the close button and clears the URL", async () => {
    const user = userEvent.setup();
    const { router, drawer } = await openDrawer();
    await user.click(must(within(drawer).getAllByRole("button", { name: copy.drawer.close })[0]));
    await waitFor(() => {
      expect(screen.queryByRole("dialog")).toBeNull();
    });
    expect(router.state.location.search).not.toHaveProperty("patient");
  });

  it("has no serious axe violations", async () => {
    const { drawer } = await openDrawer();
    await within(drawer).findByRole("note");
    expect(await seriousAxeViolations(document.body)).toEqual([]);
  });
});
