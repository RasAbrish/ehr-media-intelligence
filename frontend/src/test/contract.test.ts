/// <reference types="node" />
/**
 * docs/04 section 12: every JSON example in the contract parses with its Zod schema, and
 * the fixtures used by MSW handlers are exactly those examples.
 */
import { CurrentUserSchema, LoginRequestSchema } from "@/features/auth/schemas";
import { readdirSync, readFileSync } from "node:fs";
import path from "node:path";

import type { z } from "zod";

import {
  AuditEntryItemSchema,
  BundleSchema,
  ClinicalSummaryResponseSchema,
  PatientDetailSchema,
  PatientPageSchema,
  PatientResourcesResponseSchema,
  ResourceDetailSchema,
  SummaryFeedbackRequestSchema,
  SummaryFeedbackResponseSchema,
} from "@/features/patients/schemas";
import { QualityOverviewSchema } from "@/features/quality/schemas";
import { SearchResponseSchema } from "@/features/search/schemas";
import { ProblemSchema } from "@/lib/problem";
import {
  HealthResponseSchema,
  PipelineRunAcceptedSchema,
  ReadyResponseSchema,
  StatsResponseSchema,
} from "@/lib/system-schemas";
import { extractContractExamples } from "@/test/contract/extract";

const SCHEMAS: Record<string, z.ZodType> = {
  "2.3-1": ProblemSchema,
  "3a.1-1": LoginRequestSchema,
  "3a.1-2": CurrentUserSchema,
  "4.1-1": HealthResponseSchema,
  "4.2-1": ReadyResponseSchema,
  "4.3-1": StatsResponseSchema,
  "5.1-1": SearchResponseSchema,
  "6.1-1": PatientPageSchema,
  "6.2-1": PatientDetailSchema,
  "6.3-1": PatientResourcesResponseSchema,
  "6.4-1": ClinicalSummaryResponseSchema,
  "6.6-1": BundleSchema,
  "6.8-1": AuditEntryItemSchema,
  "7.1-1": ResourceDetailSchema,
  "8.1-1": QualityOverviewSchema,
  "9.1-1": PipelineRunAcceptedSchema,
  "9a.1-1": SummaryFeedbackRequestSchema,
  "9a.1-2": SummaryFeedbackResponseSchema,
};

const root = path.resolve(import.meta.dirname, "../..");
const examples = extractContractExamples(
  readFileSync(path.resolve(root, "../docs/04-API-CONTRACT.md"), "utf8"),
);
const fixtureDir = path.resolve(root, "src/test/fixtures/contract");

describe("API contract examples", () => {
  it("has a schema for every example in docs/04", () => {
    expect(Object.keys(examples).sort()).toEqual(Object.keys(SCHEMAS).sort());
  });

  it.each(Object.entries(SCHEMAS))("example %s parses with its schema", (name, schema) => {
    const result = schema.safeParse(examples[name]);
    expect(result.error?.issues ?? []).toEqual([]);
  });

  it("fixtures match the doc (run `pnpm contract:fixtures` after editing docs/04)", () => {
    const files = readdirSync(fixtureDir).filter((f: string) => f.endsWith(".json"));
    expect(files.map((f: string) => f.replace(/\.json$/, "")).sort()).toEqual(
      Object.keys(examples).sort(),
    );
    for (const file of files) {
      const fixture: unknown = JSON.parse(readFileSync(path.join(fixtureDir, file), "utf8"));
      expect(fixture).toEqual(examples[file.replace(/\.json$/, "")]);
    }
  });

  it("schemas reject undocumented fields", () => {
    const withExtra = { ...(examples["4.1-1"] as object), extra: true };
    expect(HealthResponseSchema.safeParse(withExtra).success).toBe(false);
  });
});
