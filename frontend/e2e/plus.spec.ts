import { expect, test } from "@playwright/test";

import { resultArticles, search, seriousViolations } from "./helpers.ts";

test("directory: sort, find, open the drawer and its data quality tab", async ({ page }) => {
  await page.goto("/patients");
  await expect(page.locator("tbody tr")).toHaveCount(25);
  await page.getByRole("button", { name: /^Sort by Name/ }).click();
  await expect(page).toHaveURL(/sort=name/);
  await expect(page.locator('th[aria-sort="ascending"]')).toContainText("Name");
  const opener = page.locator("[data-open-patient]").first();
  const name = (await opener.textContent()) ?? "";
  await page.getByRole("searchbox", { name: "Find a patient" }).fill(name);
  await expect(page.locator("tbody tr")).toHaveCount(1);
  await opener.click();
  const drawer = page.getByRole("dialog", { name });
  await drawer.getByRole("tab", { name: "Data quality" }).click();
  await expect(drawer.getByText("Info", { exact: true }).last()).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(opener).toBeFocused();
});

test("quality: tabs, and birth dates in the audit log are masked", async ({ page }) => {
  await page.goto("/quality?tab=audit&size=100");
  const table = page.getByRole("table", { name: "Audit log" });
  const births = table.locator("tbody tr").filter({ hasText: "dob" });
  await expect(births.first()).toBeVisible();
  for (const row of await births.all()) {
    for (const column of [3, 4]) {
      const value = (await row.locator("td").nth(column).innerText()).trim();
      expect(value).toMatch(/^(\d\d\*\*-\*\*-\d\d|[^\dA-Za-z]*)$/);
    }
  }
  await page.getByRole("tab", { name: "Quarantine" }).click();
  await expect(page).toHaveURL(/tab=quarantine/);
  await expect(page.getByRole("table", { name: "Quarantine" })).toBeVisible();
  expect(await seriousViolations(page)).toEqual([]);
});

test("feedback: a helpful vote is saved", async ({ page }) => {
  await page.goto("/");
  await search(page, "chronic kidney disease");
  await resultArticles(page).first().click();
  await page.getByRole("dialog").getByRole("button", { name: "Helpful", exact: true }).click();
  await expect(page.getByRole("dialog").getByText(/^Thanks\. Feedback saved/)).toBeVisible();
});

test("shortcuts: ? opens the list, Escape returns", async ({ page }) => {
  await page.goto("/quality");
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  await page.keyboard.press("Shift+Slash");
  const dialog = page.getByRole("dialog", { name: "Keyboard shortcuts" });
  await expect(dialog).toBeVisible();
  expect(await seriousViolations(page)).toEqual([]);
  await page.keyboard.press("Escape");
  await expect(dialog).toHaveCount(0);
});

test("a drawer whose chunk loads late still holds focus", async ({ page }) => {
  await page.route(/PatientDrawerBody/, async (route) => {
    await new Promise((resolve) => setTimeout(resolve, 700));
    await route.continue();
  });
  for (const width of [1280, 390]) {
    await page.setViewportSize({ width, height: 844 });
    await page.goto("/patients");
    await page.locator("[data-open-patient]").first().click();
    await expect(page.getByRole("dialog").getByRole("note")).toBeVisible();
    const inside = await page.evaluate(() =>
      Boolean(document.activeElement?.closest('[role="dialog"]')),
    );
    expect.soft(inside, `focus inside the drawer at ${width}`).toBe(true);
    await page.keyboard.press("Tab");
    const trapped = await page.evaluate(() =>
      Boolean(document.activeElement?.closest('[role="dialog"]')),
    );
    expect.soft(trapped, `Tab stays in the drawer at ${width}`).toBe(true);
  }
});

test("a page number past the end goes to the last page", async ({ page }) => {
  await page.goto("/patients?page=9");
  await expect(page).toHaveURL(/page=3/);
  await expect(page.locator("tbody tr").first()).toBeVisible();
});

test("selecting text in a directory row does not open the patient", async ({ page }) => {
  await page.goto("/patients");
  const mrn = page.locator("tbody tr").first().locator("td").nth(1).locator("span");
  await expect(mrn).toBeVisible();
  const box = await mrn.boundingBox();
  if (!box) throw new Error("no box");
  await page.mouse.move(box.x + 1, box.y + box.height / 2);
  await page.mouse.down();
  await page.mouse.move(box.x + box.width - 1, box.y + box.height / 2, { steps: 8 });
  await page.mouse.up();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(page).not.toHaveURL(/patient=/);
});
