import { readFileSync } from "node:fs";

// Initial JS is every script and module preload that index.html asks for (docs/06 section 15).
// Lazy chunks are not in index.html, so they do not count. Needs `vite build` first.
const html = readFileSync(new URL("./dist/index.html", import.meta.url), "utf8");
const initial = [...html.matchAll(/(?:src|href)="\/([^"]+\.js)"/g)].map(
  ([, file]) => `dist/${file}`,
);

// Over HTTP/1.1 every extra initial file waits for one of six connections and delays LCP.
const bundles = initial.filter((file) => file.startsWith("dist/assets/")); // not theme-init.js
if (bundles.length !== 1) throw new Error(`Expected 1 initial bundle, found ${bundles.length}`);

export default [{ name: "Initial JS (gzip)", path: initial, limit: "250 kB", gzip: true }];
