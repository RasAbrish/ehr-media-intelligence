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

  it.each([
    ["/", copy.search.idleTitle],
    ["/patients", copy.patients.title],
    ["/quality", copy.quality.title],
  ])("shows the index-empty state on %s", async (path, heading) => {
    await renderApp(path);
    expect(await screen.findByRole("heading", { level: 1, name: heading })).toBeInTheDocument();
    const status = screen.getByRole("status");
    expect(status).toHaveTextContent(copy.indexEmpty.title);
    expect(status).toHaveTextContent(copy.indexEmpty.command);
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
