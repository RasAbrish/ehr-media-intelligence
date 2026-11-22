/** docs/06 section 9: hit targets at least 32 px, 44 px on touch layouts; overlay at 20 percent. */
import { expect, test, type Page } from "@playwright/test";

import { resultArticles, search } from "./helpers.ts";

async function smallTargets(page: Page, min: number): Promise<string[]> {
  await page.waitForTimeout(400); // enter animations scale elements
  return page.evaluate((limit) => {
    const dialogs = document.querySelectorAll('[role="dialog"]');
    const scope = dialogs[dialogs.length - 1] ?? document.body;
    const found = new Set<string>();
    const selector =
      'a[href], button, select, textarea, input:not([type="hidden"]), [role="checkbox"], [role="radio"]';
    for (const element of scope.querySelectorAll<HTMLElement>(selector)) {
      if (element.closest('[aria-hidden="true"], [inert]')) continue;
      const own = element.getBoundingClientRect();
      if (own.width <= 1 || own.height <= 1 || !element.checkVisibility()) continue;
      // A control inside a label is hit through the whole label.
      const label =
        element.closest("label") ??
        (element.id ? document.querySelector(`label[for="${element.id}"]`) : null);
      const choice = element.matches('[role="checkbox"], [role="radio"], [type="radio"]');
      const box = choice && label ? label.getBoundingClientRect() : own;
      if (box.height >= limit - 0.5 && box.width >= limit - 0.5) continue;
      const name = (element.getAttribute("aria-label") ?? element.textContent).trim().slice(0, 26);
      found.add(`${element.tagName} "${name}" ${Math.round(box.width)}x${Math.round(box.height)}`);
    }
    return [...found].slice(0, 14);
  }, min);
}

for (const [width, min] of [
  [390, 44],
  [1024, 32],
] as const) {
  test(`hit targets are at least ${min} px at ${width}`, async ({ page }) => {
    test.setTimeout(120_000);
    await page.setViewportSize({ width, height: 900 });
    const check = async (state: string) => {
      expect.soft(await smallTargets(page, min), state).toEqual([]);
    };

    await page.goto("/");
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    await check("search, idle");
    await search(page, "rising creatinine with high potassium");
    await check("results");

    if (width < 768) {
      await page.getByRole("button", { name: /^Filters/ }).click();
      await expect(page.getByRole("dialog", { name: "Filters" })).toBeVisible();
      await check("filter sheet");
    } else {
      await page.getByRole("button", { name: /Any date/ }).click();
      await check("date popover");
    }
    await page.keyboard.press("Escape");
    await expect(page.getByRole("dialog")).toHaveCount(0);

    await resultArticles(page).first().click();
    const drawer = page.getByRole("dialog");
    await expect(drawer.getByRole("note")).toBeVisible();
    await check("drawer, summary");
    await drawer.getByRole("button", { name: "Not helpful", exact: true }).click();
    await check("feedback popover");
    await page.keyboard.press("Escape");
    await drawer.getByRole("tab", { name: /^Records/ }).click();
    await check("drawer, records");
    await drawer.locator("tbody tr").first().getByRole("button").click();
    await expect(page.getByRole("tab", { name: "Readable" })).toBeVisible();
    await check("record dialog");
    await page.keyboard.press("Escape");
    await drawer.getByRole("tab", { name: "Data quality" }).click();
    await expect(drawer.getByRole("status")).toBeVisible();
    await check("drawer, data quality");

    await page.goto("/patients");
    await expect(page.locator("tbody tr").first()).toBeVisible();
    await check("directory");
    await page.goto("/quality");
    await expect(page.locator("tbody tr").first()).toBeVisible();
    await check("quality");

    await page.route("**/api/search*", (route) => route.fulfill({ status: 400, body: "{}" }));
    await page.goto("/?q=failing");
    await expect(page.getByRole("alert")).toBeVisible();
    await check("error");
  });
}

test("the drawer dims the results by 20 percent", async ({ page }) => {
  await page.goto("/");
  await search(page, "potassium");
  await resultArticles(page).first().click();
  const overlay = page.locator('[data-slot="sheet-overlay"]');
  await expect
    .poll(() => overlay.evaluate((element) => getComputedStyle(element).backgroundColor))
    .toMatch(/(, |\/ )0?\.2\)$/);
});

test("the calendar uses the app tokens, not the library theme", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: /Any date/ }).click();
  const root = page.locator(".rdp-root");
  await expect(root).toBeVisible();
  const { accent, primary } = await root.evaluate((element) => ({
    accent: getComputedStyle(element).getPropertyValue("--rdp-accent-color").trim(),
    primary: getComputedStyle(element).getPropertyValue("--primary").trim(),
  }));
  expect(accent).toBe(primary);
});

test("the app never evaluates strings, so the strict script-src holds", async ({ page }) => {
  await page.addInitScript(() => {
    const seen: string[] = [];
    Object.assign(window, { cspViolations: seen });
    document.addEventListener("securitypolicyviolation", (event) => {
      seen.push(`${event.violatedDirective} ${event.blockedURI}`);
    });
  });
  // docs/09 section 5.1 without eval. Vite's dev client needs inline scripts, nginx does not.
  await page.route(
    (url) => url.pathname === "/",
    async (route) => {
      const response = await route.fetch();
      await route.fulfill({
        response,
        headers: {
          ...response.headers(),
          "content-security-policy": "script-src 'self' 'unsafe-inline'",
        },
      });
    },
  );
  await page.goto("/");
  await search(page, "potassium");
  await resultArticles(page).first().click();
  await expect(page.getByRole("dialog").getByRole("note")).toBeVisible();
  const violations = await page.evaluate(
    () => (window as unknown as { cspViolations: string[] }).cspViolations,
  );
  expect(violations).toEqual([]);
});
