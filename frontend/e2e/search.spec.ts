import { expect, test } from "@playwright/test";

import { resultArticles, resultCards, search, seriousViolations } from "./helpers.ts";

test("search, filter, open a patient, follow evidence to the source record", async ({ page }) => {
  await page.goto("/");
  await search(page, "pulmonary embolism CT angiography");
  await expect(page).toHaveURL(/q=pulmonary\+embolism/);

  await page.getByRole("button", { name: /^Type: All/ }).click();
  await page.getByRole("checkbox", { name: "Diagnostic report" }).click();
  await page.keyboard.press("Escape");
  await expect(page).toHaveURL(/type=.*DiagnosticReport/);
  await expect(resultCards(page).first()).toBeVisible();
  for (const badge of await page
    .getByRole("list", { name: "Search results" })
    .getByText("Diagnostic report", { exact: true })
    .all()) {
    await expect(badge).toBeVisible();
  }

  const first = resultCards(page).first();
  await resultArticles(page).first().click();
  const drawer = page.getByRole("dialog");
  await expect(drawer.getByRole("note")).toContainText("AI-generated summary");
  await expect(page).toHaveURL(/patient=/);

  const evidence = drawer.getByRole("button", { name: /^Open source:/ }).first();
  await evidence.click();
  await expect(drawer.getByRole("tab", { name: /^Records/ })).toHaveAttribute(
    "aria-selected",
    "true",
  );
  await expect(drawer.locator("tr[data-highlighted]")).toHaveCount(1);

  await drawer.locator("tr[data-highlighted]").getByRole("button").click();
  const record = page.getByRole("dialog").last();
  await expect(record.getByRole("tab", { name: "Readable" })).toBeVisible();
  await record.getByRole("tab", { name: "FHIR JSON" }).click();
  await expect(record.getByText(/"resourceType"/)).toBeVisible();
  await page.keyboard.press("Escape");
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(first).toBeFocused();
});

test("keyboard only: / to search, arrows to a result, Enter, ] for records, Esc back", async ({
  page,
}) => {
  await page.goto("/");
  await page.locator("body").press("/");
  await expect(page.getByRole("searchbox")).toBeFocused();
  await page.keyboard.type("rising creatinine high potassium");
  await expect(resultCards(page).first()).toBeVisible();
  await page.keyboard.press("ArrowDown");
  await expect(resultCards(page).nth(0)).toBeFocused();
  await page.keyboard.press("ArrowDown");
  await expect(resultCards(page).nth(1)).toBeFocused();
  await page.keyboard.press("Enter");
  const drawer = page.getByRole("dialog");
  await expect(drawer.getByRole("tab", { name: "Summary" })).toHaveAttribute(
    "aria-selected",
    "true",
  );
  await page.keyboard.press("]");
  await expect(drawer.getByRole("tab", { name: /^Records/ })).toHaveAttribute(
    "aria-selected",
    "true",
  );
  await page.keyboard.press("Escape");
  await expect(drawer).toHaveCount(0);
  await expect(resultCards(page).nth(1)).toBeFocused();
});

test("mobile: filters in a bottom sheet and a full-screen drawer with a back button", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  await search(page, "chest x-ray pneumonia");
  await page.getByRole("button", { name: /^Filters/ }).click();
  const sheet = page.getByRole("dialog", { name: "Filters" });
  await sheet.getByRole("checkbox", { name: "Document" }).click();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("button", { name: "Filters (1)" })).toBeVisible();
  await resultArticles(page).first().click();
  const drawer = page.getByRole("dialog");
  const box = await drawer.boundingBox();
  expect(box?.width).toBeGreaterThanOrEqual(389);
  await drawer.getByRole("button", { name: "Back to results" }).click();
  await expect(drawer).toHaveCount(0);
});

for (const scheme of ["light", "dark"] as const) {
  test(`no serious axe violations, contrast included (${scheme})`, async ({ page }) => {
    await page.emulateMedia({ colorScheme: scheme });
    await page.goto("/");
    expect(await seriousViolations(page)).toEqual([]);
    await search(page, "rising creatinine with high potassium");
    expect(await seriousViolations(page)).toEqual([]);
    await resultArticles(page).first().click();
    await expect(page.getByRole("dialog").getByRole("note")).toBeVisible();
    expect(await seriousViolations(page)).toEqual([]);
    await page
      .getByRole("dialog")
      .getByRole("tab", { name: /^Records/ })
      .click();
    expect(await seriousViolations(page)).toEqual([]);
  });
}
