/** docs/06 sections 6.1, 6.8 and 8.6: every screen fits from 320 to 2560 px. */
import { expect, test } from "@playwright/test";

const PAGES = [
  "/",
  "/?q=rising%20creatinine%20with%20high%20potassium",
  "/patients",
  "/quality",
  "/quality?tab=audit",
  "/quality?tab=quarantine",
];

for (const width of [320, 390, 768, 1024, 1232, 1240, 1280, 1366, 1440, 1920, 2560]) {
  test(`every screen fits at ${width} px`, async ({ page }) => {
    test.setTimeout(90_000);
    await page.setViewportSize({ width, height: 800 });
    for (const path of PAGES) {
      await page.goto(path);
      await expect(page.getByRole("heading", { level: 1 })).toBeAttached();
      if (path.startsWith("/?q=")) await expect(page.getByRole("article").first()).toBeVisible();
      else if (path !== "/") await expect(page.locator("tbody tr").first()).toBeVisible();

      const seen = await page.evaluate(() => {
        const main = document.querySelector("main");
        const content = main?.querySelector("section");
        if (!main || !content) throw new Error("no content");
        const rem = parseFloat(getComputedStyle(document.documentElement).fontSize);
        const visible = [...main.querySelectorAll<HTMLElement>("*")].filter((element) =>
          element.checkVisibility(),
        );
        return {
          pageScroll: document.documentElement.scrollWidth - document.documentElement.clientWidth,
          unused: (main.clientWidth - content.getBoundingClientRect().width) / rem,
          scrolling: [...main.querySelectorAll("table")]
            .map((table) => table.parentElement)
            .filter((box) => box && box.scrollWidth > box.clientWidth + 1).length,
          cut: visible
            .filter(
              (element) =>
                getComputedStyle(element).textOverflow === "ellipsis" &&
                element.clientWidth > 1 &&
                element.scrollWidth > element.clientWidth + 1 &&
                element.tagName !== "INPUT",
            )
            .map((element) => element.textContent.slice(0, 30)),
        };
      });
      expect.soft(seen.pageScroll, `${path}: page scroll`).toBeLessThanOrEqual(0);
      expect.soft(seen.unused, `${path}: unused width in rem`).toBeLessThanOrEqual(4.1);
      expect.soft(seen.scrolling, `${path}: sideways table scroll`).toBe(0);
      expect.soft(seen.cut, `${path}: cut text`).toEqual([]);
    }
  });
}

for (const [width, rem, sidebar] of [
  [768, 16, 5],
  [1024, 16, 14],
  [1920, 18, 14],
  [2560, 20, 14],
] as const) {
  test(`the sidebar is ${sidebar} rem with icons and labels at ${width} px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 600 });
    await page.goto("/patients");
    await expect(page.locator("tbody tr").first()).toBeVisible();
    const banner = page.getByRole("banner");
    await expect
      .poll(() => banner.boundingBox())
      .toEqual({ x: 0, y: 0, width: rem * sidebar, height: 600 });
    for (const name of ["Search", "Patients", "Data quality"]) {
      const link = banner.getByRole("link", { name, exact: true });
      await expect(link.locator("svg")).toBeVisible();
      await expect(link.getByText(name, { exact: true })).toBeInViewport();
    }
    await page.mouse.wheel(0, 3000);
    await expect(banner.getByRole("button", { name: /Change theme/ })).toBeInViewport();
    await expect(banner.getByRole("button", { name: "Keyboard shortcuts" })).toBeInViewport();
  });
}

test("stacked directory rows keep table roles, sorting and severity", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/patients");
  const table = page.getByRole("table", { name: "Patient directory" });
  await expect(table.getByRole("row").nth(1).getByRole("cell").first()).toBeVisible();
  await expect(table.getByRole("columnheader")).toHaveCount(8);
  const flag = table.getByText(/^(High|Moderate)/).first();
  await flag.scrollIntoViewIfNeeded();
  await expect(flag).toBeInViewport({ ratio: 1 });
  await table.getByRole("button", { name: /Sort by Name/ }).click();
  await expect(page).toHaveURL(/sort=name/);
});

for (const width of [768, 1024, 1232, 1280, 1920]) {
  test(`the sidebar opens and closes at ${width} px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 600 });
    await page.goto("/patients");
    await expect(page.locator("tbody tr").first()).toBeVisible();
    const rem = width >= 1920 ? 18 : 16;
    const banner = page.getByRole("banner");
    const startsOpen = width >= 1024;
    const states = startsOpen ? [false, true] : [true, false];
    const region = page.getByRole("table", { name: "Patient directory" }).locator("..");
    for (const open of states) {
      await banner.getByRole("button", { name: open ? "Open sidebar" : "Close sidebar" }).click();
      const check = async () => {
        const size = (open ? 14 : 5) * rem;
        await expect.poll(async () => (await banner.boundingBox())?.width).toBe(size);
        await expect.poll(async () => (await page.getByRole("main").boundingBox())?.x).toBe(size);
        await expect
          .poll(() => region.evaluate((box) => box.scrollWidth - box.clientWidth))
          .toBeLessThanOrEqual(1);
        expect(
          await banner.evaluate((box) => box.scrollWidth - box.clientWidth),
        ).toBeLessThanOrEqual(0);
        const name = open ? "Close sidebar" : "Open sidebar";
        await expect(banner.getByRole("button", { name })).toBeInViewport({ ratio: 1 });
      };
      await check();
      await page.reload();
      await expect(page.locator("tbody tr").first()).toBeVisible();
      await check();
    }
  });
}

test("a phone keeps its menu whatever the stored sidebar choice", async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem("mi-sidebar", "open");
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  await expect(page.getByRole("button", { name: "Open navigation menu" })).toBeVisible();
  await expect(page.getByRole("button", { name: /sidebar/ })).toHaveCount(0);
  expect((await page.getByRole("main").boundingBox())?.x).toBe(0);
});

for (const width of [768, 1024, 1920]) {
  test(`drawer text is never cut at ${width} px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 800 });
    await page.goto("/?q=potassium&type=DiagnosticReport");
    await page.getByRole("article").first().getByRole("heading").click();
    const drawer = page.getByRole("dialog");
    await expect(drawer.getByRole("note")).toBeVisible();
    const cut = () =>
      drawer
        .locator("*")
        .evaluateAll((elements) =>
          elements
            .filter(
              (element) =>
                element.checkVisibility() &&
                getComputedStyle(element).textOverflow === "ellipsis" &&
                element.scrollWidth > element.clientWidth + 1 &&
                element.tagName !== "INPUT",
            )
            .map((element) => element.textContent),
        );
    expect.soft(await cut(), "summary").toEqual([]);
    await drawer.getByRole("tab", { name: /^Records/ }).click();
    await expect(drawer.locator("tbody button").first()).toBeVisible();
    expect.soft(await cut(), "records").toEqual([]);
  });
}

test("short codes stay on one line inside cards", async ({ page }) => {
  await page.setViewportSize({ width: 1024, height: 800 });
  await page.goto("/quality?tab=audit");
  const code = page.getByText("date.parse.format", { exact: true }).first();
  await expect(code).toBeVisible();
  expect(await code.evaluate((element) => element.getClientRects().length)).toBe(1);
});
