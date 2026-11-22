import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { afterEach, describe, expect, it, vi } from "vitest";

import { copy } from "@/lib/copy";
import { seriousAxeViolations } from "@/test/axe";
import { DEMO_PASSWORD, DEMO_USER, problemResponse } from "@/test/msw/handlers";
import { server } from "@/test/msw/server";
import { renderApp } from "@/test/render-app";

const signedOut = () => {
  server.use(http.get("*/api/auth/me", () => problemResponse(401, "not_authenticated")));
};

afterEach(() => {
  vi.unstubAllEnvs();
});

describe("Sign-in", () => {
  it("sends a signed-out visitor to sign-in and back to the page afterwards", async () => {
    signedOut();
    const user = userEvent.setup();
    const { router } = await renderApp("/patients?q=ana");
    expect(await screen.findByRole("heading", { level: 1, name: copy.auth.title })).toBeVisible();
    expect(router.state.location.pathname).toBe("/signin");
    expect(router.state.location.search).toEqual({ next: "/patients?q=ana" });

    server.use(http.get("*/api/auth/me", () => HttpResponse.json(DEMO_USER)));
    await user.type(screen.getByLabelText(copy.auth.email), DEMO_USER.email);
    await user.type(screen.getByLabelText(copy.auth.password), DEMO_PASSWORD);
    await user.click(screen.getByRole("button", { name: copy.auth.submit }));
    expect(await screen.findByRole("heading", { name: copy.patients.title })).toBeVisible();
    expect(router.state.location.href).toBe("/patients?q=ana");
  });

  it("never returns to another site", async () => {
    signedOut();
    const { router } = await renderApp("/signin?next=//evil.example/x");
    await screen.findByRole("heading", { level: 1, name: copy.auth.title });
    expect(router.state.location.search).toEqual({ next: "/" });
  });

  it("shows one message for a wrong login and keeps the email", async () => {
    signedOut();
    const user = userEvent.setup();
    await renderApp("/signin");
    await user.type(await screen.findByLabelText(copy.auth.email), DEMO_USER.email);
    await user.type(screen.getByLabelText(copy.auth.password), "not the password");
    await user.click(screen.getByRole("button", { name: copy.auth.submit }));
    expect(await screen.findByText(copy.auth.failed)).toBeVisible();
    expect(screen.getByLabelText(copy.auth.email)).toHaveValue(DEMO_USER.email);
    expect(screen.getByLabelText(copy.auth.password)).toHaveAttribute("aria-invalid", "true");
  });

  it("shows and hides the password", async () => {
    signedOut();
    const user = userEvent.setup();
    await renderApp("/signin");
    const field = await screen.findByLabelText(copy.auth.password);
    const toggle = screen.getByRole("button", { name: copy.auth.show });
    expect(field).toHaveAttribute("type", "password");
    await user.click(toggle);
    expect(field).toHaveAttribute("type", "text");
    expect(toggle).toHaveAttribute("aria-pressed", "true");
  });

  it("fills the demo login in demo builds", async () => {
    vi.stubEnv("VITE_DEMO_EMAIL", DEMO_USER.email);
    vi.stubEnv("VITE_DEMO_PASSWORD", DEMO_PASSWORD);
    signedOut();
    const user = userEvent.setup();
    await renderApp("/signin");
    const box = await screen.findByRole("region", { name: copy.auth.demoTitle });
    await user.click(within(box).getByRole("button", { name: copy.auth.useDemo }));
    expect(screen.getByLabelText(copy.auth.email)).toHaveValue(DEMO_USER.email);
    expect(screen.getByLabelText(copy.auth.password)).toHaveValue(DEMO_PASSWORD);
  });

  it("goes straight to the app when already signed in", async () => {
    const { router } = await renderApp("/signin?next=/quality");
    await waitFor(() => {
      expect(router.state.location.pathname).toBe("/quality");
    });
  });

  it("signs out, forgets cached data and returns to sign-in", async () => {
    const user = userEvent.setup();
    const { router, queryClient } = await renderApp("/");
    await screen.findByRole("heading", { level: 1 });
    signedOut();
    await user.click(
      within(screen.getByRole("banner")).getByRole("button", { name: copy.auth.signOut }),
    );
    await screen.findByRole("heading", { level: 1, name: copy.auth.title });
    expect(router.state.location.pathname).toBe("/signin");
    expect(
      queryClient
        .getQueryCache()
        .findAll()
        .filter((q) => q.state.data),
    ).toHaveLength(0);
  });

  it("returns to sign-in when the session ends while working", async () => {
    const { router } = await renderApp("/patients");
    await screen.findByRole("heading", { name: copy.patients.title });
    signedOut();
    server.use(http.get("*/api/patients", () => problemResponse(401, "not_authenticated")));
    await router.navigate({ to: "/patients", search: { q: "zz" } });
    await screen.findByRole("heading", { level: 1, name: copy.auth.title });
    expect(router.state.location.search).toEqual({ next: "/patients?q=zz" });
  });

  it.each(["light", "dark"] as const)("has no serious axe violations in %s", async (theme) => {
    window.localStorage.setItem("mi-theme", theme);
    signedOut();
    const { container } = await renderApp("/signin");
    await screen.findByRole("heading", { level: 1, name: copy.auth.title });
    expect(await seriousAxeViolations(container)).toEqual([]);
  });
});
