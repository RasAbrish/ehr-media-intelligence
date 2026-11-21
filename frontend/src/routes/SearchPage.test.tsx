import { act, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { delay, http, HttpResponse } from "msw";

import { copy } from "@/lib/copy";
import { seriousAxeViolations } from "@/test/axe";
import { must } from "@/test/must";
import { fixtures } from "@/test/msw/fixtures";
import { problemResponse } from "@/test/msw/handlers";
import { server } from "@/test/msw/server";
import { renderApp } from "@/test/render-app";

const firstName = fixtures.search.results[0]?.patient.display_name ?? "";

async function resultsList() {
  return screen.findByRole("list", { name: copy.search.resultsLabel });
}

describe("Search page", () => {
  it("searches as you type after the debounce and puts the query in the URL (FR-5.1)", async () => {
    const user = userEvent.setup();
    const seen: string[] = [];
    server.use(
      http.post("*/api/search", async ({ request }) => {
        seen.push(((await request.json()) as { query: string }).query);
        return HttpResponse.json(fixtures.search);
      }),
    );
    const { router } = await renderApp("/");
    await user.type(screen.getByRole("searchbox", { name: copy.search.inputLabel }), "kidney");
    expect(await resultsList()).toBeInTheDocument();
    expect(seen).toEqual(["kidney"]); // one request after typing stops, not one per key
    expect(router.state.location.search).toMatchObject({ q: "kidney" });
    const meta = copy.search.meta(2, 41, "hybrid");
    const announced = screen
      .getAllByText(meta)
      .filter((el) => el.getAttribute("aria-live") === "polite");
    expect(announced).toHaveLength(1); // one persistent live region announces the count
  });

  it("restores the search from the URL", async () => {
    await renderApp("/?q=potassium");
    expect(screen.getByRole("searchbox")).toHaveValue("potassium");
    expect(await screen.findByText(firstName)).toBeInTheDocument();
  });

  it("keeps the previous results visible while the next search runs", async () => {
    const user = userEvent.setup();
    await renderApp("/?q=potassium");
    await screen.findByText(firstName);
    server.use(
      http.post("*/api/search", async () => {
        await delay(400);
        return HttpResponse.json({ ...fixtures.search, results: [], total: 0 });
      }),
    );
    await user.type(screen.getByRole("searchbox"), " level");
    await waitFor(() => {
      expect(screen.getByRole("status", { name: copy.search.searching })).toBeInTheDocument();
    });
    expect(screen.getByText(firstName)).toBeInTheDocument();
    expect(
      await screen.findByRole("heading", { name: copy.search.noResultsTitle }),
    ).toBeInTheDocument();
  });

  it("shows the idle hero below two characters and runs example searches", async () => {
    const user = userEvent.setup();
    const { router } = await renderApp("/?q=a");
    expect(
      screen.getByRole("heading", { level: 1, name: copy.search.idleTitle }),
    ).toBeInTheDocument();
    const example = copy.search.examples[1];
    await user.click(screen.getByRole("button", { name: example }));
    expect(screen.getByRole("searchbox")).toHaveValue(example);
    expect(router.state.location.search).toMatchObject({ q: example });
    expect(await resultsList()).toBeInTheDocument();
  });

  it("shows no results with a clear-filters action when filters are active", async () => {
    const user = userEvent.setup();
    server.use(
      http.post("*/api/search", () =>
        HttpResponse.json({ ...fixtures.search, results: [], total: 0 }),
      ),
    );
    const { router } = await renderApp("/?q=zzz&type=Observation");
    expect(
      await screen.findByRole("heading", { name: copy.search.noResultsTitle }),
    ).toBeInTheDocument();
    const main = screen.getByRole("main");
    await user.click(
      must(within(main).getAllByRole("button", { name: copy.filters.clear }).at(-1)),
    );
    await waitFor(() => {
      expect(router.state.location.search).not.toHaveProperty("type");
    });
  });

  it("shows a server error with the request id and retries", async () => {
    const user = userEvent.setup();
    server.use(http.post("*/api/search", () => problemResponse(500, "internal_error")));
    await renderApp("/?q=chest");
    const alert = await screen.findByRole("alert", {}, { timeout: 4000 });
    expect(alert).toHaveTextContent(copy.errors.title);
    expect(alert).toHaveTextContent(fixtures.problem.request_id);
    server.resetHandlers();
    await user.click(within(alert).getByRole("button", { name: copy.errors.retry }));
    expect(await screen.findByText(firstName)).toBeInTheDocument();
  });

  it("explains a network failure", async () => {
    server.use(http.post("*/api/search", () => HttpResponse.error()));
    await renderApp("/?q=chest");
    expect(await screen.findByText(copy.errors.network, {}, { timeout: 4000 })).toBeInTheDocument();
  });

  it("shows the pipeline hint when nothing is indexed", async () => {
    server.use(
      http.post("*/api/search", () => problemResponse(503, "search_index_empty")),
      http.get("*/api/ready", () =>
        HttpResponse.json({ ...fixtures.ready, counts: { ...fixtures.ready.counts, chunks: 0 } }),
      ),
    );
    await renderApp("/?q=chest");
    expect(
      await screen.findByText(copy.indexEmpty.title, {}, { timeout: 4000 }),
    ).toBeInTheDocument();
    expect(screen.getByText(copy.indexEmpty.command)).toBeInTheDocument();
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("filters by type and date through the URL (FR-5.4)", async () => {
    const user = userEvent.setup();
    let query = "";
    server.use(
      http.post("*/api/search", ({ request }) => {
        query = new URL(request.url).search;
        return HttpResponse.json(fixtures.search);
      }),
    );
    const { router } = await renderApp("/?q=chest&from=2024-06-01&to=2024-12-31");
    await resultsList();
    expect(query).toContain("date_from=2024-06-01");
    expect(query).toContain("date_to=2024-12-31");
    await user.click(screen.getByRole("button", { name: /^Type: All/ }));
    await user.click(
      await screen.findByRole("checkbox", { name: copy.resourceLabels.DiagnosticReport }),
    );
    await waitFor(() => {
      expect(router.state.location.search).toMatchObject({ type: ["DiagnosticReport"] });
    });
    await waitFor(() => {
      expect(query).toContain("resource_type=DiagnosticReport");
    });
    const chips = screen.getByRole("list", { name: copy.filters.active });
    await user.click(
      within(chips).getByRole("button", {
        name: copy.filters.remove("Jun 1, 2024 to Dec 31, 2024"),
      }),
    );
    await waitFor(() => {
      expect(router.state.location.search).not.toHaveProperty("from");
    });
  });

  it("supports the keyboard model: / focuses, ↓ enters results, arrows move, Esc clears", async () => {
    const user = userEvent.setup();
    await renderApp("/?q=potassium");
    await resultsList();
    const input = screen.getByRole("searchbox");
    act(() => {
      input.blur();
    });
    await user.keyboard("/");
    expect(input).toHaveFocus();
    await user.keyboard("{ArrowDown}");
    const cards = within(await resultsList()).getAllByRole("button", { name: /^Open / });
    expect(cards[0]).toHaveFocus();
    expect(cards[1]).toHaveAttribute("tabindex", "-1");
    await user.keyboard("{ArrowDown}");
    expect(cards[1]).toHaveFocus();
    await user.keyboard("{Home}");
    expect(cards[0]).toHaveFocus();
    await user.keyboard("{End}");
    expect(cards.at(-1)).toHaveFocus();
    input.focus();
    await user.keyboard("{Escape}");
    expect(input).toHaveValue("");
  });

  it("opens the drawer with Enter and returns focus to the card on Escape (FR-5.3, FR-5.6)", async () => {
    const user = userEvent.setup();
    const { router } = await renderApp("/?q=potassium");
    const cards = within(await resultsList()).getAllByRole("button", { name: /^Open / });
    cards[0]?.focus();
    await user.keyboard("{Enter}");
    const drawer = await screen.findByRole("dialog", { name: fixtures.patient.display_name });
    expect(router.state.location.search).toHaveProperty("patient");
    expect(within(drawer).getByRole("tab", { name: copy.drawer.tabs.summary })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    await user.keyboard("{Escape}");
    await waitFor(() => {
      expect(screen.queryByRole("dialog")).toBeNull();
    });
    expect(router.state.location.search).not.toHaveProperty("patient");
    await waitFor(() => {
      expect(cards[0]).toHaveFocus();
    });
  });

  it("says it is retrying after a 429, then asks the user to retry", async () => {
    let calls = 0;
    server.use(
      http.post("*/api/search", () => {
        calls += 1;
        return HttpResponse.json(
          { ...fixtures.problem, status: 429, code: "rate_limited" },
          {
            status: 429,
            headers: { "Content-Type": "application/problem+json", "Retry-After": "1" },
          },
        );
      }),
    );
    await renderApp("/?q=chest");
    expect(await screen.findByText(copy.errors.rateLimited(1))).toBeInTheDocument();
    expect(
      await screen.findByText(copy.errors.rateLimitedFinal(1), {}, { timeout: 4000 }),
    ).toBeInTheDocument();
    expect(calls).toBe(2);
  });

  it("marks only the card that opened the drawer as selected", async () => {
    const user = userEvent.setup();
    const sameDoc = must(fixtures.search.results[0]);
    server.use(
      http.post("*/api/search", () =>
        HttpResponse.json({
          ...fixtures.search,
          total: 2,
          results: [
            sameDoc,
            { ...sameDoc, rank: 2, resource: { ...sameDoc.resource, resource_id: "other-record" } },
          ],
        }),
      ),
    );
    await renderApp("/?q=potassium");
    const articles = within(await resultsList()).getAllByRole("article");
    await user.click(within(must(articles[1])).getByRole("heading"));
    await screen.findByRole("dialog");
    const all = within(
      screen.getByRole("list", { name: copy.search.resultsLabel, hidden: true }),
    ).getAllByRole("article", { hidden: true });
    expect(all.map((a) => a.hasAttribute("data-selected"))).toEqual([false, true]);
  });

  it("has no serious axe violations with results", async () => {
    const { container } = await renderApp("/?q=potassium");
    await screen.findByText(firstName);
    expect(await seriousAxeViolations(container)).toEqual([]);
  });
});
