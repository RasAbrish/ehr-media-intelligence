import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { copy } from "@/lib/copy";
import { seriousAxeViolations } from "@/test/axe";
import { renderApp } from "@/test/render-app";

describe("AppShell", () => {
  it("renders the top bar with brand, navigation and theme control", async () => {
    await renderApp("/");
    const banner = screen.getByRole("banner");
    expect(within(banner).getByRole("link", { name: copy.product })).toBeInTheDocument();
    const nav = within(banner).getByRole("navigation", { name: copy.nav.label });
    for (const label of [copy.nav.search, copy.nav.patients, copy.nav.quality]) {
      expect(within(nav).getByRole("link", { name: label })).toBeInTheDocument();
    }
    expect(within(banner).getByRole("button", { name: /change theme/i })).toBeInTheDocument();
  });

  it("marks the current page in the navigation", async () => {
    await renderApp("/quality");
    const nav = screen.getByRole("navigation", { name: copy.nav.label });
    expect(within(nav).getByRole("link", { name: copy.nav.quality })).toHaveAttribute(
      "aria-current",
      "page",
    );
    expect(within(nav).getByRole("link", { name: copy.nav.search })).not.toHaveAttribute(
      "aria-current",
    );
  });

  it("shows the search hero with example searches on /", async () => {
    await renderApp("/");
    expect(
      await screen.findByRole("heading", { level: 1, name: copy.search.idleTitle }),
    ).toBeInTheDocument();
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
    const examples = screen.getByRole("list", { name: copy.search.examplesLabel });
    expect(within(examples).getAllByRole("button")).toHaveLength(copy.search.examples.length);
  });

  it.each([
    ["/patients", copy.patients.title],
    ["/quality", copy.quality.title],
  ])("shows the page heading on %s", async (path, heading) => {
    await renderApp(path);
    expect(await screen.findByRole("heading", { level: 1, name: heading })).toBeInTheDocument();
  });

  it("keeps Search current while a query is in the URL", async () => {
    await renderApp("/?q=potassium");
    const nav = screen.getByRole("navigation", { name: copy.nav.label });
    expect(within(nav).getByRole("link", { name: copy.nav.search })).toHaveAttribute(
      "aria-current",
      "page",
    );
  });

  it("shows the stats pill from /stats", async () => {
    await renderApp("/");
    const banner = screen.getByRole("banner");
    expect(await within(banner).findByText(copy.stats.pill(60, 310))).toBeInTheDocument();
  });

  it("shows a not-found page for unknown paths", async () => {
    await renderApp("/nope");
    expect(await screen.findByRole("heading", { name: copy.notFound.title })).toBeInTheDocument();
  });

  it("navigates between pages with the keyboard", async () => {
    const user = userEvent.setup();
    const { router } = await renderApp("/");
    const nav = screen.getByRole("navigation", { name: copy.nav.label });
    within(nav).getByRole("link", { name: copy.nav.patients }).focus();
    await user.keyboard("{Enter}");
    expect(await screen.findByRole("heading", { name: copy.patients.title })).toBeInTheDocument();
    expect(router.state.location.pathname).toBe("/patients");
  });

  it("offers a skip link to the main content", async () => {
    await renderApp("/");
    const skip = screen.getByRole("link", { name: copy.skipLink });
    expect(skip).toHaveAttribute("href", "#main");
    expect(document.getElementById("main")).toBeInTheDocument();
  });

  it.each(["light", "dark"] as const)("has no serious axe violations in %s theme", async (t) => {
    window.localStorage.setItem("mi-theme", t);
    const { container } = await renderApp("/");
    await screen.findByRole("heading", { level: 1 });
    expect(document.documentElement.classList.contains("dark")).toBe(t === "dark");
    expect(await seriousAxeViolations(container)).toEqual([]);
  });
});
