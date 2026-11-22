import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";

import { copy } from "@/lib/copy";
import { seriousAxeViolations } from "@/test/axe";
import { fixtures } from "@/test/msw/fixtures";
import { problemResponse } from "@/test/msw/handlers";
import { must } from "@/test/must";
import { server } from "@/test/msw/server";
import { renderApp } from "@/test/render-app";

const row = must(fixtures.directory.items[0]);

function capture() {
  const seen: URLSearchParams[] = [];
  server.use(
    http.get("*/api/patients", ({ request }) => {
      const params = new URL(request.url).searchParams;
      seen.push(params);
      return HttpResponse.json({ ...fixtures.directory, page: Number(params.get("page") ?? 1) });
    }),
  );
  return seen;
}

const table = () => screen.findByRole("table", { name: copy.directory.label });

describe("Patient directory (FR-5.7)", () => {
  it("shows each column and the row range", async () => {
    await renderApp("/patients");
    const scope = within(await table());
    expect(await scope.findByText(row.display_name)).toBeInTheDocument();
    expect(scope.getByText(row.mrn)).toBeInTheDocument();
    expect(scope.getByText("Feb 4, 2025")).toBeInTheDocument();
    expect(scope.getByText("12")).toBeInTheDocument();
    expect(scope.getByText(row.chief_concern ?? "")).toBeInTheDocument();
    expect(scope.getByText(copy.ai.badge)).toBeInTheDocument();
    expect(scope.getByText(`${copy.ai.severity.high} · 1`)).toBeInTheDocument();
    expect(screen.getByText(copy.table.range(1, 25, 60))).toBeInTheDocument();
  });

  it("sorts on the server and announces the order", async () => {
    const user = userEvent.setup();
    const seen = capture();
    const { router } = await renderApp("/patients");
    const button = await screen.findByRole("button", {
      name: copy.records.sortBy(copy.directory.columns.name),
    });
    await user.click(button);
    await waitFor(() => {
      expect(seen.at(-1)?.get("sort")).toBe("name");
    });
    expect(seen.at(-1)?.get("order")).toBe("asc");
    expect(router.state.location.search).toMatchObject({ sort: "name", order: "asc" });
    expect(button.closest("th")).toHaveAttribute("aria-sort", "ascending");
  });

  it("searches after the debounce and returns to the first page", async () => {
    const user = userEvent.setup();
    const seen = capture();
    await renderApp("/patients?page=2");
    await table();
    await user.type(screen.getByRole("searchbox", { name: copy.directory.search }), "doe");
    await waitFor(() => {
      expect(seen.at(-1)?.get("q")).toBe("doe");
    });
    expect(seen.at(-1)?.get("page")).toBe("1");
    expect(seen.filter((p) => p.get("q"))).toHaveLength(1);
  });

  it("pages and changes the page size", async () => {
    const user = userEvent.setup();
    const seen = capture();
    await renderApp("/patients");
    await table();
    await user.click(await screen.findByRole("button", { name: copy.table.next }));
    expect(await screen.findByText(copy.table.range(26, 50, 60))).toBeInTheDocument();
    await user.selectOptions(screen.getByLabelText(copy.table.pageSize), "100");
    await waitFor(() => {
      expect(seen.at(-1)?.get("page_size")).toBe("100");
    });
    expect(seen.at(-1)?.get("page")).toBe("1");
  });

  it("filters to identity conflicts", async () => {
    const user = userEvent.setup();
    const seen = capture();
    await renderApp("/patients");
    await table();
    await user.click(screen.getByRole("checkbox", { name: copy.directory.conflictOnly }));
    await waitFor(() => {
      expect(seen.at(-1)?.get("conflict_only")).toBe("true");
    });
  });

  it("opens the same drawer and returns focus to the row", async () => {
    const user = userEvent.setup();
    const { router } = await renderApp("/patients");
    const open = await screen.findByRole("button", { name: copy.directory.open(row.display_name) });
    await user.click(open);
    await screen.findByRole("dialog", { name: fixtures.patient.display_name });
    expect(router.state.location.search).toMatchObject({ patient: row.patient_key });
    await user.keyboard("{Escape}");
    await waitFor(() => {
      expect(open).toHaveFocus();
    });
  });

  it("shows no matches", async () => {
    server.use(
      http.get("*/api/patients", () =>
        HttpResponse.json({ ...fixtures.directory, items: [], total: 0, total_pages: 1 }),
      ),
    );
    await renderApp("/patients?q=nobody");
    expect(await screen.findByText(copy.directory.noMatch)).toBeInTheDocument();
  });

  it("shows the pipeline hint when there are no patients", async () => {
    server.use(
      http.get("*/api/patients", () =>
        HttpResponse.json({ ...fixtures.directory, items: [], total: 0, total_pages: 1 }),
      ),
    );
    await renderApp("/patients");
    expect(await screen.findByText(copy.indexEmpty.title)).toBeInTheDocument();
  });

  it("names the failure", async () => {
    server.use(http.get("*/api/patients", () => problemResponse(422, "validation_error")));
    await renderApp("/patients");
    expect(await screen.findByText(copy.errors.directoryTitle)).toBeInTheDocument();
  });

  it("has no serious axe violations", async () => {
    const { container } = await renderApp("/patients");
    await screen.findByText(row.display_name);
    expect(await seriousAxeViolations(container)).toEqual([]);
  });
});
