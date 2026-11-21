/**
 * Visual QA screenshots (docs/06 section 11) at 390, 1024 and 1440 px in light and dark.
 * Run on demand: `VISUAL=1 pnpm e2e visual`. Files land in test-results/visual/.
 */
import { expect, test, type Page } from "@playwright/test";

import { resultArticles, search } from "./helpers.ts";

test.skip(!process.env.VISUAL, "visual QA runs on demand (VISUAL=1)");

const WIDTHS = [390, 1024, 1440] as const;
const SCHEMES = ["light", "dark"] as const;
const QUERY = "rising creatinine with high potassium";

async function shot(page: Page, name: string): Promise<void> {
  await page.waitForTimeout(350); // let transitions settle
  await page.screenshot({ path: `test-results/visual/${name}.png` });
}

for (const scheme of SCHEMES) {
  for (const width of WIDTHS) {
    test(`${scheme} ${width}`, async ({ page }) => {
      await page.emulateMedia({ colorScheme: scheme, reducedMotion: "reduce" });
      await page.setViewportSize({ width, height: width === 390 ? 844 : 900 });
      const tag = `${scheme}-${width}`;

      await page.goto("/");
      await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
      await shot(page, `${tag}-01-idle`);

      await search(page, QUERY);
      await shot(page, `${tag}-02-results`);

      await page.getByRole("searchbox").fill("zzqx unrelated words");
      await page.goto("/?q=potassium&from=1990-01-01&to=1990-01-02");
      await expect(page.getByRole("heading", { name: "No records match" })).toBeVisible();
      await shot(page, `${tag}-03-no-results`);

      await page.route("**/api/search*", (route) =>
        route.fulfill({
          status: 500,
          contentType: "application/problem+json",
          body: JSON.stringify({
            type: "https://ehr-mip.local/problems/internal_error",
            title: "Internal server error",
            status: 500,
            detail: "An unexpected error occurred.",
            instance: "/search",
            code: "internal_error",
            request_id: "6f1c2b0e-9d7a-4c55-8a51-0f2b1d9e3c11",
            errors: [],
          }),
        }),
      );
      await page.goto("/?q=error+state");
      await expect(page.getByRole("alert")).toBeVisible({ timeout: 15_000 });
      await shot(page, `${tag}-04-error`);
      await page.unroute("**/api/search*");

      await page.goto("/");
      await search(page, QUERY);
      await resultArticles(page).first().click();
      const drawer = page.getByRole("dialog");
      await expect(drawer.getByRole("note")).toBeVisible();
      await shot(page, `${tag}-05-drawer-summary`);

      await drawer.getByRole("tab", { name: /^Records/ }).click();
      await expect(drawer.getByRole("table")).toBeVisible();
      await shot(page, `${tag}-06-drawer-records`);
    });
  }
}
