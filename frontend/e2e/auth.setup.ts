/** Sign in once through the page and keep the session for the other specs (docs/04 section 3a). */
import { expect, test as setup } from "@playwright/test";

import { E2E_EMAIL, E2E_PASSWORD, SESSION_FILE } from "./session.ts";

setup("sign in", async ({ page }) => {
  await page.goto("/");
  await expect(page).toHaveURL(/\/signin/);
  await page.getByLabel("Email").fill(E2E_EMAIL);
  await page.getByLabel("Password", { exact: true }).fill(E2E_PASSWORD);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(
    "Search across every patient record",
  );
  await page.context().storageState({ path: SESSION_FILE });
});
