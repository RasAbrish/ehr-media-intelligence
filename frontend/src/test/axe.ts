import axe from "axe-core";

/**
 * Run axe on a rendered container and return serious or critical violations.
 * Color contrast is checked in the browser (Playwright), since jsdom does not compute styles.
 */
export async function seriousAxeViolations(container: Element): Promise<axe.Result[]> {
  const results = await axe.run(container, {
    rules: { "color-contrast": { enabled: false } },
  });
  return results.violations.filter(
    (violation) => violation.impact === "serious" || violation.impact === "critical",
  );
}
