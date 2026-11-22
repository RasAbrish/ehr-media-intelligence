/** docs/09 section 5.1 as nginx really serves it; Vite's dev server has no CSP. */
import { expect, test } from "@playwright/test";

import { resultArticles, search } from "./helpers.ts";

test.skip(!process.env.E2E_BASE_URL, "needs the production server (E2E_BASE_URL)");

test("no screen violates the production CSP", async ({ page }) => {
  const violations: string[] = [];
  await page.exposeFunction("reportViolation", (text: string) => violations.push(text));
  await page.addInitScript(() => {
    document.addEventListener("securitypolicyviolation", (event) => {
      const { reportViolation } = window as unknown as { reportViolation: (t: string) => void };
      reportViolation(`${event.violatedDirective} ${event.blockedURI}`);
    });
  });
  const response = await page.goto("/");
  expect(response?.headers()["content-security-policy"]).toContain("script-src 'self';");

  await search(page, "potassium");
  await resultArticles(page).first().click();
  const drawer = page.getByRole("dialog");
  await expect(drawer.getByRole("note")).toBeVisible();
  await drawer.getByRole("button", { name: "Not helpful", exact: true }).click();
  await page.keyboard.press("Escape");
  await drawer.getByRole("tab", { name: /^Records/ }).click();
  await drawer.locator("tbody tr").first().getByRole("button").click();
  await expect(page.getByRole("tab", { name: "Readable" })).toBeVisible();

  await page.goto("/patients");
  await expect(page.locator("tbody tr").first()).toBeVisible();
  await page.goto("/quality");
  await expect(page.locator("tbody tr").first()).toBeVisible();
  await page.goto("/");
  await page.getByRole("button", { name: /Any date/ }).click();
  await expect(page.locator(".rdp-root")).toBeVisible();
  expect(violations).toEqual([]);
});
