import { describe, expect, it } from "vitest";

const stories = Object.values(
  import.meta.glob<string>("/src/**/*.stories.tsx", {
    query: "?raw",
    import: "default",
    eager: true,
  }),
).join("\n");
const common = Object.keys(import.meta.glob("/src/components/common/*.tsx"))
  .filter((file) => !/\.(test|stories)\.tsx$/.test(file))
  .map((file) => file.replace(/^.*\/(\w+)\.tsx$/, "$1"));
const features = [
  "ResultCard",
  "ResultList",
  "FilterBar",
  "SummaryPanel",
  "SummaryFeedback",
  "ConfidenceMeter",
  "KpiStrip",
  "DirectoryTable",
  "SignInPhoto",
];

describe("Storybook coverage (FR-8.4, docs/06 section 16)", () => {
  it.each([...common, ...features])("%s has a story", (name) => {
    expect(stories).toMatch(new RegExp(`<${name}\\b|component: ${name}\\b`));
  });
});
