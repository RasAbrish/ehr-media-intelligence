import { existsSync, readFileSync } from "node:fs";
import { createRequire } from "node:module";
import path from "node:path";

import { expect, test, type Page } from "@playwright/test";
import type { AxeResults } from "axe-core";

const ROOT = path.resolve(import.meta.dirname, "../storybook-static");
const ORIGIN = "http://storybook.test";
const AXE = createRequire(import.meta.url).resolve("axe-core/axe.min.js");

interface Entry {
  id: string;
  type: "story" | "docs";
}
const index = JSON.parse(readFileSync(path.join(ROOT, "index.json"), "utf8")) as {
  entries: Record<string, Entry>;
};
const entries = Object.values(index.entries);

/** The static build is served from disk: no server, no port, no network. */
async function open(page: Page, query: string): Promise<string[]> {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.route("**/*", async (route) => {
    const url = new URL(route.request().url());
    if (url.origin !== ORIGIN) return route.abort();
    const file = path.join(ROOT, decodeURIComponent(url.pathname));
    if (!file.startsWith(ROOT + path.sep) || !existsSync(file)) {
      return route.fulfill({ status: 404, body: "" });
    }
    return route.fulfill({ path: file });
  });
  await page.goto(`${ORIGIN}/iframe.html?${query}`);
  return errors;
}

for (const story of entries.filter((entry) => entry.type === "story")) {
  for (const theme of ["light", "dark"] as const) {
    test(`${story.id} (${theme})`, async ({ page }) => {
      await page.emulateMedia({ reducedMotion: "reduce", colorScheme: theme });
      const errors = await open(
        page,
        `id=${story.id}&viewMode=story&globals=theme:${theme};a11y.manual:!true`,
      );
      // "finished" comes after the play function; a failed one ends in another phase.
      const phase = () =>
        page.evaluate(() => {
          const preview = (
            window as unknown as {
              __STORYBOOK_PREVIEW__?: { currentRender?: { phase?: string } };
            }
          ).__STORYBOOK_PREVIEW__;
          return preview?.currentRender?.phase ?? "loading";
        });
      await expect.poll(phase).toBe("finished");
      expect(await page.evaluate(() => document.documentElement.classList.contains("dark"))).toBe(
        theme === "dark",
      );
      // Let enter animations end, or axe measures half-transparent text.
      await page.evaluate(() =>
        Promise.all(
          document
            .getAnimations()
            .filter((animation) => animation.effect?.getTiming().iterations !== Infinity)
            .map((animation) => animation.finished.catch(() => undefined)),
        ),
      );
      await page.addScriptTag({ path: AXE });
      const violations = await page.evaluate(async () => {
        const { axe } = window as unknown as {
          axe: { run: (context: unknown, options: unknown) => Promise<AxeResults> };
        };
        const result = await axe.run(
          { include: document.body, exclude: [[".sb-wrapper"], ["[data-base-ui-focus-guard]"]] },
          // A story is a fragment, so page structure rules do not apply.
          { rules: { region: { enabled: false } } },
        );
        return result.violations
          .filter((v) => v.impact === "serious" || v.impact === "critical")
          .map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(" ")).join(", ")}`);
      });
      expect(violations).toEqual([]);
      expect(errors).toEqual([]);
    });
  }
}

test("the token reference page renders", async ({ page }) => {
  const docs = entries.find((entry) => entry.type === "docs" && entry.id.includes("tokens"));
  const errors = await open(page, `id=${docs?.id ?? "missing"}&viewMode=docs`);
  await expect(page.getByText("destructive", { exact: true })).toBeVisible();
  expect(errors).toEqual([]);
});
