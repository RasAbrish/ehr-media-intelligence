/** Sign-in page (docs/06 section 6.1a) and the session gate. */
import { expect, test } from "@playwright/test";

import { seriousViolations } from "./helpers.ts";
import { E2E_EMAIL, E2E_PASSWORD } from "./session.ts";

test.describe("signed out", () => {
  test.use({ storageState: { cookies: [], origins: [] } });

  for (const width of [320, 390, 768, 1024, 1440, 1920, 2560]) {
    test(`the sign-in page fits at ${width} px`, async ({ page }) => {
      await page.setViewportSize({ width, height: 800 });
      await page.goto("/quality?tab=audit");
      await expect(page).toHaveURL(/\/signin\?next=/);
      await expect(page.getByRole("heading", { level: 1, name: "Sign in" })).toBeVisible();
      const photo = page.locator("picture img");
      await expect.poll(() => photo.evaluate((img: HTMLImageElement) => img.complete)).toBe(true);
      const box = await photo.boundingBox();
      if (width >= 1024) {
        expect(box?.width).toBe(width / 2);
        expect(box?.height).toBe(800);
      } else {
        expect(box?.width).toBe(width);
      }
      const scroll = await page.evaluate(
        () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
      );
      expect(scroll).toBeLessThanOrEqual(0);
      await expect(page.getByRole("button", { name: "Sign in" })).toBeInViewport();
    });
  }

  for (const scheme of ["light", "dark"] as const) {
    test(`the sign-in page passes axe in ${scheme}`, async ({ page }) => {
      await page.emulateMedia({ colorScheme: scheme });
      await page.goto("/signin");
      await expect(page.getByRole("heading", { level: 1, name: "Sign in" })).toBeVisible();
      expect(await seriousViolations(page)).toEqual([]);
    });
  }

  test("a keyboard user signs in and returns to the page they asked for", async ({ page }) => {
    await page.goto("/patients?q=a");
    await expect(page.getByRole("heading", { level: 1, name: "Sign in" })).toBeVisible();
    await page.getByLabel("Email").focus();
    await page.keyboard.type(E2E_EMAIL);
    await page.keyboard.press("Tab");
    await page.keyboard.type(E2E_PASSWORD);
    await page.keyboard.press("Enter");
    await expect(page.getByRole("heading", { level: 1, name: "Patients" })).toBeVisible();
    await expect(page).toHaveURL(/\/patients\?q=a$/);
  });

  test("a wrong password shows one message", async ({ page }) => {
    await page.goto("/signin");
    await page.getByLabel("Email").fill(E2E_EMAIL);
    await page.getByLabel("Password", { exact: true }).fill("not the password");
    await page.getByRole("button", { name: "Sign in" }).click();
    await expect(page.getByText("Email or password is incorrect.")).toBeVisible();
  });

  test("the API refuses data without a session", async ({ request }) => {
    const response = await request.get("/api/stats");
    expect(response.status()).toBe(401);
  });
});

test("signing out ends the session", async ({ browser }) => {
  // A fresh sign-in, so the shared session of the other specs stays valid.
  const context = await browser.newContext({ storageState: { cookies: [], origins: [] } });
  const page = await context.newPage();
  await page.goto("/signin");
  await page.getByLabel("Email").fill(E2E_EMAIL);
  await page.getByLabel("Password", { exact: true }).fill(E2E_PASSWORD);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  await page.getByRole("banner").getByRole("button", { name: "Sign out" }).click();
  await expect(page).toHaveURL(/\/signin/);
  await page.goto("/patients");
  await expect(page).toHaveURL(/\/signin\?next=/);
  await context.close();
});
