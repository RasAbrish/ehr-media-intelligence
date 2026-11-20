import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { applyTheme, readStoredPreference, resolveTheme, THEME_STORAGE_KEY } from "@/app/theme";
import { renderApp } from "@/test/render-app";

describe("theme helpers", () => {
  it.each([
    ["light", false, "light"],
    ["light", true, "light"],
    ["dark", false, "dark"],
    ["system", true, "dark"],
    ["system", false, "light"],
  ] as const)("resolves %s with prefersDark=%s to %s", (preference, prefersDark, expected) => {
    expect(resolveTheme(preference, prefersDark)).toBe(expected);
  });

  it("ignores invalid stored values", () => {
    window.localStorage.setItem(THEME_STORAGE_KEY, "purple");
    expect(readStoredPreference()).toBe("system");
  });

  it("applies the dark class and color scheme", () => {
    const root = document.createElement("html");
    applyTheme("dark", root);
    expect(root).toHaveClass("dark");
    expect(root.style.colorScheme).toBe("dark");
    applyTheme("light", root);
    expect(root).not.toHaveClass("dark");
  });
});

describe("ThemeToggle", () => {
  it("switches to dark and remembers the choice", async () => {
    const user = userEvent.setup();
    await renderApp("/");
    expect(document.documentElement).not.toHaveClass("dark");

    await user.click(screen.getByRole("button", { name: /change theme/i }));
    await user.click(await screen.findByRole("menuitemradio", { name: "Dark" }));

    expect(document.documentElement).toHaveClass("dark");
    expect(window.localStorage.getItem(THEME_STORAGE_KEY)).toBe("dark");
    expect(screen.getByRole("button", { name: /change theme \(dark\)/i })).toBeInTheDocument();
  });

  it("can return to following the system", async () => {
    const user = userEvent.setup();
    window.localStorage.setItem(THEME_STORAGE_KEY, "dark");
    await renderApp("/");
    expect(document.documentElement).toHaveClass("dark");

    await user.click(screen.getByRole("button", { name: /change theme/i }));
    await user.click(await screen.findByRole("menuitemradio", { name: "System" }));

    expect(document.documentElement).not.toHaveClass("dark"); // jsdom system theme is light
    expect(window.localStorage.getItem(THEME_STORAGE_KEY)).toBe("system");
  });
});
