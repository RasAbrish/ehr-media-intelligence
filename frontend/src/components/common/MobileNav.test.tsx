import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { copy } from "@/lib/copy";
import { renderApp } from "@/test/render-app";

describe("MobileNav", () => {
  it("lists every page and marks the current one", async () => {
    const user = userEvent.setup();
    await renderApp("/quality");
    await user.click(screen.getByRole("button", { name: copy.nav.menu }));
    const items = await screen.findAllByRole("menuitemradio");
    expect(items.map((item) => item.textContent)).toEqual([
      copy.nav.search,
      copy.nav.patients,
      copy.nav.quality,
    ]);
    for (const item of items) expect(item.querySelector("svg")).toBeInTheDocument();
    expect(screen.getByRole("menuitemradio", { name: copy.nav.quality })).toHaveAttribute(
      "aria-checked",
      "true",
    );
  });

  it("navigates to the chosen page", async () => {
    const user = userEvent.setup();
    const { router } = await renderApp("/");
    await user.click(screen.getByRole("button", { name: copy.nav.menu }));
    await user.click(await screen.findByRole("menuitemradio", { name: copy.nav.patients }));
    expect(await screen.findByRole("heading", { name: copy.patients.title })).toBeInTheDocument();
    expect(router.state.location.pathname).toBe("/patients");
  });
});
