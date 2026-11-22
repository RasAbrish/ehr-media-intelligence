import { useQuery, type UseQueryResult } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import type { ReactNode } from "react";
import type { z } from "zod";

import { DataTable, serverColumns } from "@/components/common/DataTable";
import { EmptyState } from "@/components/common/EmptyState";
import { ErrorState } from "@/components/common/ErrorState";
import { Pagination } from "@/components/common/Pagination";
import { Skeleton } from "@/components/ui/skeleton";
import { auditQuery, quarantineQuery, validationQuery } from "@/features/quality/api";
import type {
  AuditEntryWithPatientSchema,
  QuarantineItemSchema,
  ValidationIssueItemSchema,
} from "@/features/quality/schemas";
import { IssueSeverity } from "@/features/quality/SeverityControls";
import type { PatientRef } from "@/lib/common-schemas";
import { copy } from "@/lib/copy";
import type { PageParams } from "@/lib/query-keys";

type Issue = z.infer<typeof ValidationIssueItemSchema>;
type Audit = z.infer<typeof AuditEntryWithPatientSchema>;
type Quarantined = z.infer<typeof QuarantineItemSchema>;

interface PanelProps {
  params: PageParams;
  onPage: (page: number) => void;
  onPageSize: (size: number) => void;
}

function PatientLink({ patient }: { patient: PatientRef | null }) {
  if (!patient) return <span className="text-muted-foreground">{copy.quality.noPatient}</span>;
  return (
    <Link
      to="/patients"
      search={{ patient: patient.patient_key }}
      className="inline-flex min-h-8 items-center whitespace-nowrap text-foreground underline underline-offset-2 max-md:min-h-11"
    >
      {patient.display_name}
    </Link>
  );
}

const mono = (value: string | null) => (
  <span className="font-mono text-mono break-all whitespace-normal">{value ?? ""}</span>
);
const preview = (value: string) => (
  <span className="block min-w-64 font-mono text-mono break-all whitespace-normal">{value}</span>
);
const token = (value: string) => (
  <span className="font-mono text-mono whitespace-nowrap">{value}</span>
);
const prose = (value: string) => <span className="block min-w-48 whitespace-normal">{value}</span>;
const labels = copy.quality.columns;

const issue = serverColumns<Issue>();
const ISSUE_COLUMNS = issue.columns([
  issue.accessor("severity", {
    header: labels.severity,
    cell: ({ row }) => <IssueSeverity severity={row.original.severity} />,
  }),
  issue.accessor("code", { header: labels.code, cell: ({ row }) => token(row.original.code) }),
  issue.accessor((row) => row.patient.display_name, {
    id: "patient",
    header: labels.patient,
    cell: ({ row }) => <PatientLink patient={row.original.patient} />,
  }),
  issue.accessor("resource_type", {
    header: labels.type,
    cell: ({ row }) => row.original.resource_type,
  }),
  issue.accessor("message", {
    header: labels.message,
    cell: ({ row }) => prose(row.original.message),
  }),
  issue.accessor("path", { header: labels.path, cell: ({ row }) => mono(row.original.path) }),
]);

const audit = serverColumns<Audit>();
const AUDIT_COLUMNS = audit.columns([
  audit.accessor("severity", {
    header: labels.severity,
    cell: ({ row }) => <IssueSeverity severity={row.original.severity} />,
  }),
  audit.accessor("rule", { header: labels.rule, cell: ({ row }) => token(row.original.rule) }),
  audit.accessor("field", { header: labels.field, cell: ({ row }) => row.original.field ?? "" }),
  audit.accessor("before", { header: labels.before, cell: ({ row }) => mono(row.original.before) }),
  audit.accessor("after", { header: labels.after, cell: ({ row }) => mono(row.original.after) }),
  audit.accessor((row) => row.patient?.display_name ?? "", {
    id: "patient",
    header: labels.patient,
    cell: ({ row }) => <PatientLink patient={row.original.patient} />,
  }),
  audit.accessor("message", {
    header: labels.message,
    cell: ({ row }) => prose(row.original.message),
  }),
]);

const quarantined = serverColumns<Quarantined>();
const QUARANTINE_COLUMNS = quarantined.columns([
  quarantined.accessor("source_locator", {
    header: labels.source,
    cell: ({ row }) => token(row.original.source_locator),
  }),
  quarantined.accessor("reason", {
    header: labels.reason,
    cell: ({ row }) => token(row.original.reason),
  }),
  quarantined.accessor("payload_preview", {
    header: labels.preview,
    cell: ({ row }) => preview(row.original.payload_preview),
  }),
]);

interface ListResult<T> {
  items: T[];
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
}

function Listing<T>({
  query,
  empty,
  children,
  onPage,
  onPageSize,
}: Omit<PanelProps, "params"> & {
  query: UseQueryResult<ListResult<T>>;
  empty: { title: string; body: string };
  children: (items: T[]) => ReactNode;
}) {
  if (query.isError) {
    return (
      <ErrorState
        title={copy.errors.qualityTitle}
        error={query.error}
        onRetry={() => void query.refetch()}
      />
    );
  }
  if (!query.data) return <Skeleton className="h-64 w-full" />;
  const { items, page, page_size, total, total_pages } = query.data;
  if (total === 0) return <EmptyState title={empty.title} description={empty.body} />;
  return (
    <div className="flex flex-col gap-2">
      {children(items)}
      <Pagination
        page={page}
        pageSize={page_size}
        total={total}
        totalPages={total_pages}
        onPage={onPage}
        onPageSize={onPageSize}
      />
    </div>
  );
}

export function IssuesPanel({ params, ...paging }: PanelProps) {
  const query = useQuery(validationQuery(params));
  const empty = params.severity
    ? { title: copy.quality.noMatchTitle, body: copy.quality.noMatchBody }
    : { title: copy.quality.noIssuesTitle, body: copy.quality.noIssuesBody };
  return (
    <Listing query={query} empty={empty} {...paging}>
      {(items) => (
        <DataTable
          label={copy.quality.tabs.issues}
          columns={ISSUE_COLUMNS}
          rows={items}
          rowId={(item) => String(item.id)}
        />
      )}
    </Listing>
  );
}

export function AuditPanel({ params, ...paging }: PanelProps) {
  const query = useQuery(auditQuery(params));
  const empty = { title: copy.quality.noMatchTitle, body: copy.quality.noMatchBody };
  return (
    <Listing query={query} empty={empty} {...paging}>
      {(items) => (
        <DataTable
          label={copy.quality.tabs.audit}
          columns={AUDIT_COLUMNS}
          rows={items}
          rowId={(item) => String(item.id)}
        />
      )}
    </Listing>
  );
}

export function QuarantinePanel({ params, ...paging }: PanelProps) {
  const query = useQuery(quarantineQuery(params));
  const empty = { title: copy.quality.noQuarantineTitle, body: copy.quality.noQuarantineBody };
  return (
    <Listing query={query} empty={empty} {...paging}>
      {(items) => (
        <DataTable
          label={copy.quality.tabs.quarantine}
          columns={QUARANTINE_COLUMNS}
          rows={items}
          rowId={(item) => String(item.id)}
        />
      )}
    </Listing>
  );
}
