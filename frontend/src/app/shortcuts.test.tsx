import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { copy } from "@/lib/copy";
import { seriousAxeViolations } from "@/test/axe";
import { must } from "@/test/must";
import { fixtures } from "@/test/msw/fixtures";
import { renderApp } from "@/test/render-app";

const dialogName = () => ({ name: copy.shortcuts.title });

describe("shortcuts dialog (FR-5.9, docs/06 section 8.4)", () => {
  it("opens with ? and lists the whole keyboard model", async () => {
    const user = userEvent.setup();
    await renderApp("/quality");
    await user.keyboard("?");
    const dialog = await screen.findByRole("dialog", dialogName());
    expect(copy.shortcuts.rows).toHaveLength(9);
    for (const row of copy.shortcuts.rows) {
      expect(within(dialog).getByText(row.action)).toBeInTheDocument();
    }
    expect(await seriousAxeViolations(dialog)).toEqual([]);
    await user.keyboard("{Escape}");
    await waitFor(() => {
      expect(screen.queryByRole("dialog")).toBeNull();
    });
  });

  it("types ? into a field instead of opening", async () => {
    const user = userEvent.setup();
    await renderApp("/");
    const input = screen.getByRole("searchbox");
    await user.type(input, "?");
    expect(input).toHaveValue("?");
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("opens from the top bar and returns focus to its button", async () => {
    const user = userEvent.setup();
    await renderApp("/");
    const button = screen.getByRole("button", { name: copy.shortcuts.open });
    await user.click(button);
    await screen.findByRole("dialog", dialogName());
    await user.keyboard("{Escape}");
    await waitFor(() => {
      expect(button).toHaveFocus();
    });
  });

  it("opens over the drawer, and Escape closes only the dialog", async () => {
    const user = userEvent.setup();
    const { router } = await renderApp(`/patients?patient=${fixtures.patient.patient_key}`);
    await screen.findByRole("dialog", { name: fixtures.patient.display_name });
    await user.keyboard("?");
    await screen.findByRole("dialog", dialogName());
    await user.keyboard("{Escape}");
    await waitFor(() => {
      expect(screen.queryByRole("dialog", dialogName())).toBeNull();
    });
    expect(
      await screen.findByRole("dialog", { name: fixtures.patient.display_name }),
    ).toBeInTheDocument();
    expect(router.state.location.search).toHaveProperty("patient");
  });
});

describe("focus search from anywhere", () => {
  it.each(["/", "{Control>}k{/Control}"])("%s on the quality page goes to search", async (keys) => {
    const user = userEvent.setup();
    const { router } = await renderApp("/quality");
    await user.keyboard(keys);
    await waitFor(() => {
      expect(screen.getByRole("searchbox", { name: copy.search.inputLabel })).toHaveFocus();
    });
    expect(router.state.location.pathname).toBe("/");
  });

  it("focuses the directory's own field on /patients", async () => {
    const user = userEvent.setup();
    const { router } = await renderApp("/patients");
    await user.keyboard("/");
    expect(screen.getByRole("searchbox", { name: copy.directory.search })).toHaveFocus();
    expect(router.state.location.pathname).toBe("/patients");
  });
});

describe("first-run tip (FR-8.6, docs/06 section 12.4)", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("shows on the first visit and stays dismissed", async () => {
    const user = userEvent.setup();
    const view = await renderApp("/");
    expect(screen.getByText(copy.tip.body)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: copy.tip.dismiss }));
    expect(screen.queryByText(copy.tip.body)).toBeNull();
    expect(screen.getByRole("searchbox")).toHaveFocus();
    view.unmount();
    await renderApp("/");
    expect(screen.queryByText(copy.tip.body)).toBeNull();
  });

  it("still dismisses when storage is blocked", async () => {
    const user = userEvent.setup();
    vi.spyOn(
      must(Object.getPrototypeOf(window.localStorage) as Storage),
      "setItem",
    ).mockImplementation(() => {
      throw new Error("blocked");
    });
    await renderApp("/");
    await user.click(screen.getByRole("button", { name: copy.tip.dismiss }));
    expect(screen.queryByText(copy.tip.body)).toBeNull();
  });
});
