/** Regressions from the heuristic review (docs/ux/heuristic-review.md, severity 3). */
import { expect, test, type Page } from "@playwright/test";

import { resultArticles, search, seriousViolations } from "./helpers.ts";

const QUERY = "rising creatinine with high potassium";

async function openDrawer(page: Page) {
  await page.goto("/");
  await search(page, QUERY);
  await resultArticles(page).first().getByRole("heading").click();
  const drawer = page.getByRole("dialog");
  await expect(drawer.getByRole("note")).toBeVisible();
  return drawer;
}

for (const width of [390, 1440]) {
  test(`the patient stays identified at the end of the drawer (${width})`, async ({ page }) => {
    await page.setViewportSize({ width, height: 600 });
    await page.emulateMedia({ reducedMotion: "reduce" });
    const drawer = await openDrawer(page);
    const name = drawer.getByRole("heading", { level: 2 }).first();
    await drawer.getByRole("button", { name: "Helpful", exact: true }).scrollIntoViewIfNeeded();
    await drawer.evaluate((el) => {
      el.scrollTop = el.scrollHeight;
    });
    await expect(name).toBeInViewport({ ratio: 1 });
  });
}

test("the FHIR JSON pane scrolls by keyboard", async ({ page }) => {
  const drawer = await openDrawer(page);
  await drawer.getByRole("tab", { name: /^Records/ }).click();
  await drawer.locator("tbody button").first().click();
  await page.getByRole("tab", { name: "FHIR JSON" }).click();
  const pane = page.getByRole("region", { name: "FHIR JSON" });
  await expect(pane).toBeVisible();
  await pane.focus();
  await expect(pane).toBeFocused();
  expect(await seriousViolations(page)).toEqual([]);
});

test("record titles and values are readable on a phone", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  const drawer = await openDrawer(page);
  await drawer.getByRole("tab", { name: /^Records/ }).click();
  await expect(drawer.locator("tbody button").first()).toBeVisible();
  const clipped = await drawer
    .locator("tbody button, tbody button + span")
    .evaluateAll((els) =>
      els.filter((el) => el.scrollWidth > el.clientWidth + 1).map((el) => el.textContent),
    );
  expect(clipped).toEqual([]);
});

test("audit values do not wrap one letter per line on a phone", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/quality?tab=audit");
  const row = page.getByRole("table", { name: "Audit log" }).locator("tbody tr").first();
  await expect(row).toBeVisible();
  for (const column of [3, 4]) {
    const box = await row.locator("td").nth(column).boundingBox();
    expect(box?.width).toBeGreaterThanOrEqual(96);
  }
});

test("Retry does not cover the error message", async ({ page }) => {
  await page.setViewportSize({ width: 1024, height: 800 });
  await page.route("**/api/patients/*/summary", (route) =>
    route.fulfill({
      status: 500,
      contentType: "application/problem+json",
      body: JSON.stringify({
        type: "https://ehr-mip.local/problems/internal_error",
        title: "Internal server error",
        status: 500,
        detail: "Test",
        instance: "/summary",
        code: "internal_error",
        request_id: "9f1c2d3e-0000-4000-8000-000000000001",
        errors: [],
      }),
    }),
  );
  await page.goto("/");
  await search(page, QUERY);
  await resultArticles(page).first().getByRole("heading").click();
  const alert = page.getByRole("dialog").getByRole("alert");
  await expect(alert).toContainText("Summary could not be loaded", { timeout: 8000 });
  const text = await alert.locator("p").first().boundingBox();
  const retry = await alert.getByRole("button", { name: "Retry" }).boundingBox();
  if (!text || !retry) throw new Error("not rendered");
  const overlaps =
    retry.x < text.x + text.width &&
    text.x < retry.x + retry.width &&
    retry.y < text.y + text.height &&
    text.y < retry.y + retry.height;
  expect(overlaps).toBe(false);
});

for (const scheme of ["light", "dark"] as const) {
  test(`control boundaries have 3:1 contrast (${scheme})`, async ({ page }) => {
    await page.emulateMedia({ colorScheme: scheme, reducedMotion: "reduce" });
    await page.goto("/patients");
    await expect(page.locator("tbody tr").first()).toBeVisible();
    for (const control of [page.getByRole("searchbox"), page.getByRole("checkbox")]) {
      const ratio = await control.evaluate((el) => {
        const context = document.createElement("canvas").getContext("2d", {
          willReadFrequently: true,
        });
        if (!context) throw new Error("no canvas");
        // Paint the ancestors' backgrounds, then the border, as the browser composites them.
        const paint = (colors: string[]) => {
          context.clearRect(0, 0, 1, 1);
          for (const color of colors) {
            context.fillStyle = color;
            context.fillRect(0, 0, 1, 1);
          }
          const [r, g, b] = [...context.getImageData(0, 0, 1, 1).data].map((value) => {
            const c = value / 255;
            return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
          }) as [number, number, number];
          return 0.2126 * r + 0.7152 * g + 0.0722 * b;
        };
        const behind: string[] = [];
        for (let node = el.parentElement; node; node = node.parentElement) {
          behind.unshift(getComputedStyle(node).backgroundColor);
        }
        const style = getComputedStyle(el);
        const outside = paint(behind);
        const border = paint([...behind, style.backgroundColor, style.borderTopColor]);
        return (Math.max(outside, border) + 0.05) / (Math.min(outside, border) + 0.05);
      });
      expect(ratio).toBeGreaterThanOrEqual(3);
    }
  });
}
