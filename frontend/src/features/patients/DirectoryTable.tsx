import type { z } from "zod";

import { AiBadge } from "@/components/common/AiBadge";
import { DataTable, serverColumns } from "@/components/common/DataTable";
import { SeverityBadge } from "@/components/common/SeverityBadge";
import type { DirectorySort } from "@/features/patients/directory-params";
import type { PatientListItemSchema } from "@/features/patients/schemas";
import { copy } from "@/lib/copy";
import { ageSex, formatDate } from "@/lib/format";

export type DirectoryItem = z.infer<typeof PatientListItemSchema>;

const helper = serverColumns<DirectoryItem>();
const labels = copy.directory.columns;

const columns = helper.columns([
  helper.accessor("display_name", {
    id: "name",
    header: labels.name,
    cell: ({ row }) => (
      <span className="flex flex-col items-start">
        <button
          type="button"
          data-open-patient
          aria-label={copy.directory.open(row.original.display_name)}
          className="min-h-8 rounded-sm text-left font-medium hover:underline focus-visible:outline-2 focus-visible:outline-ring max-md:min-h-11"
        >
          {row.original.display_name}
        </button>
        {row.original.identity_conflict ? (
          <span className="rounded-sm border border-warning/40 bg-warning/15 px-1.5 text-meta text-warning-foreground dark:text-warning">
            {copy.card.conflict}
          </span>
        ) : null}
      </span>
    ),
  }),
  helper.accessor("mrn", {
    id: "mrn",
    header: labels.mrn,
    cell: ({ row }) => <span className="font-mono text-mono">{row.original.mrn}</span>,
  }),
  helper.accessor("birth_date", {
    id: "birth_date",
    header: labels.birth,
    cell: ({ row }) => (
      <span className="tabular-nums">{formatDate(row.original.birth_date) ?? copy.ai.undated}</span>
    ),
  }),
  helper.accessor("age", {
    id: "age",
    header: labels.age,
    enableSorting: false,
    cell: ({ row }) => {
      const who = ageSex(row.original.age, row.original.gender);
      return <span title={who.long}>{who.short}</span>;
    },
  }),
  helper.accessor("last_activity", {
    id: "last_activity",
    header: labels.activity,
    cell: ({ row }) => (
      <span className="tabular-nums">
        {formatDate(row.original.last_activity) ?? copy.ai.undated}
      </span>
    ),
  }),
  helper.accessor("resource_count", {
    id: "resource_count",
    header: labels.records,
    cell: ({ row }) => row.original.resource_count,
  }),
  helper.accessor("chief_concern", {
    id: "chief_concern",
    header: labels.concern,
    enableSorting: false,
    cell: ({ row }) =>
      row.original.chief_concern ? (
        <span
          className="flex max-w-72 min-w-48 items-center gap-2"
          title={row.original.chief_concern}
        >
          <AiBadge />
          <span className="truncate">{row.original.chief_concern}</span>
        </span>
      ) : (
        <span className="text-muted-foreground italic">{copy.ai.missingTitle}</span>
      ),
  }),
  helper.accessor((row) => row.anomaly_counts.high, {
    id: "anomalies",
    header: labels.anomalies,
    enableSorting: false,
    cell: ({ row }) => {
      const { high, moderate } = row.original.anomaly_counts;
      return (
        <span className="flex gap-1">
          {high ? <SeverityBadge severity="high" suffix={String(high)} /> : null}
          {moderate ? <SeverityBadge severity="moderate" suffix={String(moderate)} /> : null}
        </span>
      );
    },
  }),
]);

interface DirectoryTableProps {
  items: DirectoryItem[];
  sort: DirectorySort;
  order: "asc" | "desc";
  onSort: (sort: DirectorySort, order: "asc" | "desc") => void;
  onOpen: (key: string, opener: HTMLElement) => void;
}

/** Patient directory table (docs/06 section 8.5, FR-5.7). */
export function DirectoryTable({ items, sort, order, onSort, onOpen }: DirectoryTableProps) {
  return (
    <DataTable
      label={copy.directory.label}
      columns={columns}
      rows={items}
      rowId={(item) => item.patient_key}
      numeric={["resource_count"]}
      sorting={[{ id: sort, desc: order === "desc" }]}
      onSortingChange={([next]) => {
        if (next) onSort(next.id as DirectorySort, next.desc ? "desc" : "asc");
      }}
      onRowClick={(item, row) => {
        onOpen(item.patient_key, row.querySelector<HTMLElement>("[data-open-patient]") ?? row);
      }}
    />
  );
}
