import { readFileSync } from "node:fs";
import { createRequire } from "node:module";

import { expect, type Page } from "@playwright/test";

const require = createRequire(import.meta.url);
const AXE_SOURCE = readFileSync(require.resolve("axe-core/axe.min.js"), "utf8");

export async function search(page: Page, query: string): Promise<void> {
  await page.getByRole("searchbox", { name: "Search patient records" }).fill(query);
  await expect(page.getByRole("list", { name: "Search results" })).toBeVisible();
}

/** The card buttons: the keyboard path (focus, Enter). */
export function resultCards(page: Page) {
  return page.getByRole("list", { name: "Search results" }).getByRole("button", { name: /^Open / });
}

/** The card surfaces a mouse user clicks (the text sits above the card button). */
export function resultArticles(page: Page) {
  return page.getByRole("list", { name: "Search results" }).getByRole("article");
}

/** Serious or critical axe violations, including color contrast (real browser rendering). */
export async function seriousViolations(page: Page): Promise<string[]> {
  // Evaluated over CDP: a script tag would be refused by the production CSP, as intended.
  await page.evaluate(AXE_SOURCE);
  const ids = await page.evaluate(async () => {
    const result = await (
      window as unknown as {
        axe: {
          run: (c: Document) => Promise<{
            violations: { id: string; impact: string; nodes: { target: string[] }[] }[];
          }>;
        };
      }
    ).axe.run(document);
    return result.violations
      .filter((v) => v.impact === "serious" || v.impact === "critical")
      .map(
        (v) =>
          `${v.id}: ${v.nodes
            .map((n) => n.target.join(" "))
            .slice(0, 3)
            .join(" | ")}`,
      );
  });
  return ids;
}
