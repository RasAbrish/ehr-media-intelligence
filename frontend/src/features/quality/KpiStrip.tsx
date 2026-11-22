import type { z } from "zod";

import type { QualityOverviewSchema } from "@/features/quality/schemas";
import { copy } from "@/lib/copy";

/** Six KPI tiles (docs/06 section 6.10). */
export function KpiStrip({ overview }: { overview: z.infer<typeof QualityOverviewSchema> }) {
  const { ingestion, validation } = overview;
  const { info, warning, error } = validation.issues_by_severity;
  const labels = copy.quality.kpis;
  const tiles = [
    [labels.ingested, ingestion.records_read],
    [labels.duplicates, ingestion.exact_duplicates_removed + ingestion.near_duplicates_removed],
    [labels.merged, ingestion.identities_merged],
    [labels.conflicts, ingestion.identity_conflicts],
    [labels.valid, copy.quality.validOf(validation.valid_bundles, validation.bundles)],
    [labels.issues, info + warning + error],
  ] as const;
  return (
    <ul
      aria-label={copy.quality.kpiLabel}
      className="grid grid-cols-2 gap-2 md:grid-cols-3 xl:grid-cols-6"
    >
      {tiles.map(([label, value]) => (
        <li key={label} className="flex flex-col gap-1 rounded-xl border bg-card p-3">
          <span className="text-title tabular-nums">{value}</span>
          <span className="text-meta text-muted-foreground">{label}</span>
        </li>
      ))}
    </ul>
  );
}
