/**
 * The app's Zod. Object schemas decide on JIT when they are built, so this must run first:
 * the JIT uses `new Function`, which the production CSP (`script-src 'self'`) reports.
 * Import `z` from here, never from "zod".
 */
import { z } from "zod";

z.config({ jitless: true });

export { z };
