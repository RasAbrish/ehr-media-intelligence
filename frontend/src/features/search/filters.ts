import { format, startOfYear, subDays, subMonths, subYears } from "date-fns";

import type { SearchableType } from "@/lib/contract-enums";
import { copy } from "@/lib/copy";

export const FILTER_TYPES: SearchableType[] = [
  "DocumentReference",
  "DiagnosticReport",
  "Observation",
  "ClinicalSummary",
];

export interface FilterValue {
  types: SearchableType[];
  from: string | null;
  to: string | null;
}

export const iso = (date: Date) => format(date, "yyyy-MM-dd");

export function datePresets(today: Date) {
  return [
    {
      id: "last30",
      label: copy.filters.presets.last30,
      from: iso(subDays(today, 30)),
      to: iso(today),
    },
    {
      id: "last6m",
      label: copy.filters.presets.last6m,
      from: iso(subMonths(today, 6)),
      to: iso(today),
    },
    {
      id: "lastYear",
      label: copy.filters.presets.lastYear,
      from: iso(subYears(today, 1)),
      to: iso(today),
    },
    {
      id: "thisYear",
      label: copy.filters.presets.thisYear,
      from: iso(startOfYear(today)),
      to: iso(today),
    },
  ] as const;
}

export function typeSummary(types: SearchableType[]): string {
  if (types.length === 0) return copy.filters.typeAll;
  if (types.length === 1 && types[0]) return copy.resourceLabels[types[0]];
  return copy.filters.typeMany(types.length);
}

export function activeFilterCount(value: FilterValue): number {
  return value.types.length + (value.from || value.to ? 1 : 0);
}
