/** Where auth.setup.ts keeps the signed-in browser state for the other specs. */
export const SESSION_FILE = "e2e/.auth/session.json";

/** scripts/e2e_api.py creates this account; for a running stack set E2E_EMAIL and E2E_PASSWORD. */
export const E2E_EMAIL = process.env.E2E_EMAIL ?? "e2e@example.org";
export const E2E_PASSWORD = process.env.E2E_PASSWORD ?? "e2e-test-password";
