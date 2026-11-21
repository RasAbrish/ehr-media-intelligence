/**
 * Pull every JSON example out of docs/04-API-CONTRACT.md: fenced ```json blocks and
 * inline "Example: `{...}`" lines. Names are "{section}-{n}", for example "6.2-1".
 * No imports, so `scripts/extract-contract-fixtures.ts` can run it with plain Node.
 */
const HEADING = /^#{2,4}\s+(\d+[a-z]?(?:\.\d+)*)\b/;
const INLINE = /^Example(?: item)?:\s*`(\{.*\})`\s*$/;

export function extractContractExamples(markdown: string): Record<string, unknown> {
  const examples: Record<string, unknown> = {};
  const counts: Record<string, number> = {};
  let section = "0";
  let block: string[] | null = null;

  const add = (text: string) => {
    counts[section] = (counts[section] ?? 0) + 1;
    examples[`${section}-${counts[section]}`] = JSON.parse(text) as unknown;
  };

  for (const line of markdown.split("\n")) {
    if (block !== null) {
      if (line.trim() === "```") {
        add(block.join("\n"));
        block = null;
      } else {
        block.push(line);
      }
      continue;
    }
    const heading = HEADING.exec(line);
    if (heading?.[1]) {
      section = heading[1];
      continue;
    }
    if (line.trim() === "```json") {
      block = [];
      continue;
    }
    const inline = INLINE.exec(line.trim());
    if (inline?.[1]) add(inline[1]);
  }
  return examples;
}
