/** "Most recent record" questions (docs/ux/heuristic-review.md F19). */
import { expect, test } from "@playwright/test";

import { resultArticles, search } from "./helpers.ts";

test("finds the most recent imaging report mentioning a finding", async ({ page }) => {
  await page.goto("/?type=DiagnosticReport");
  await search(page, "pulmonary embolism");
  await page.getByRole("combobox", { name: "Sort by" }).selectOption("newest");
  await expect(page).toHaveURL(/sort=newest/);
  await expect(resultArticles(page).first()).toContainText("Jan 11, 2025");
});

test("does the same by keyboard only", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  await page.keyboard.press("/");
  await page.keyboard.type("CT chest pulmonary embolism");
  await expect(resultArticles(page).first()).toBeVisible();
  const sort = page.getByRole("combobox", { name: "Sort by" });
  for (let i = 0; i < 25; i++) {
    if (await sort.evaluate((el) => el === document.activeElement)) break;
    await page.keyboard.press("Tab");
  }
  await expect(sort).toBeFocused();
  await page.keyboard.press("n"); // type-ahead in a native select
  await expect(page).toHaveURL(/sort=newest/);
  await expect(resultArticles(page).first()).toContainText("Jan 11, 2025");
  await page.keyboard.press("Tab");
  for (let i = 0; i < 3; i++) {
    if (await page.evaluate(() => document.activeElement?.hasAttribute("data-card-button"))) break;
    await page.keyboard.press("Tab");
  }
  await page.keyboard.press("Enter");
  await expect(page.getByRole("dialog")).toBeVisible();
});
