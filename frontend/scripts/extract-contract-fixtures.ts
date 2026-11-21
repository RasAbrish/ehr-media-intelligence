/**
 * Write every JSON example in docs/04-API-CONTRACT.md to src/test/fixtures/contract/.
 * Run: `pnpm contract:fixtures`. The contract test fails when the files drift from the doc.
 */
import { mkdirSync, readdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import path from "node:path";

import { extractContractExamples } from "../src/test/contract/extract.ts";

const root = path.resolve(import.meta.dirname, "..");
const doc = path.resolve(root, "../docs/04-API-CONTRACT.md");
const target = path.resolve(root, "src/test/fixtures/contract");

mkdirSync(target, { recursive: true });
for (const file of readdirSync(target)) rmSync(path.join(target, file));
const examples = extractContractExamples(readFileSync(doc, "utf8"));
for (const [name, value] of Object.entries(examples)) {
  writeFileSync(path.join(target, `${name}.json`), `${JSON.stringify(value, null, 2)}\n`);
}
console.log(`Wrote ${Object.keys(examples).length} fixtures to ${target}`);
