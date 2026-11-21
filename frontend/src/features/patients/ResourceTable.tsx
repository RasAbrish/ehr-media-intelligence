import {
  columnFilteringFeature,
  createColumnHelper,
  createFilteredRowModel,
  createSortedRowModel,
  filterFn_equalsString,
  filterFn_includesString,
  globalFilteringFeature,
  rowSortingFeature,
  sortFn_alphanumeric,
  tableFeatures,
  useTable,
  type SortingState,
} from "@tanstack/react-table";
import { ArrowDownIcon, ArrowUpDownIcon, ArrowUpIcon } from "lucide-react";
import { useEffect, useId, useMemo, useRef, useState } from "react";

import { EmptyState } from "@/components/common/EmptyState";
import { ResourceTypeBadge } from "@/components/common/ResourceTypeBadge";
import { Input } from "@/components/ui/input";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { PatientResourceItem } from "@/features/patients/schemas";
import { copy } from "@/lib/copy";
import { formatDate } from "@/lib/format";
import { cn } from "@/lib/utils";

const features = tableFeatures({
  rowSortingFeature,
  sortedRowModel: createSortedRowModel(),
  columnFilteringFeature,
  globalFilteringFeature,
  filteredRowModel: createFilteredRowModel(),
  sortFns: { alphanumeric: sortFn_alphanumeric },
  filterFns: { includesString: filterFn_includesString, equalsString: filterFn_equalsString },
});

const helper = createColumnHelper<typeof features, PatientResourceItem>();
const columns = helper.columns([
  helper.accessor("resource_type", {
    id: "type",
    header: copy.records.columns.type,
    filterFn: "equalsString",
    sortFn: "alphanumeric",
    enableGlobalFilter: false,
  }),
  helper.accessor((row) => row.date ?? undefined, {
    id: "date",
    header: copy.records.columns.date,
    sortFn: "alphanumeric",
    sortUndefined: "last", // undated records stay last in both directions, like the API
    enableGlobalFilter: false,
  }),
  helper.accessor((row) => `${row.title} ${row.summary_line ?? ""}`, {
    id: "title",
    header: copy.records.columns.title,
    sortFn: "alphanumeric",
    filterFn: "includesString",
  }),
  helper.accessor((row) => (row.is_valid ? copy.records.valid : copy.records.invalid), {
    id: "status",
    header: copy.records.columns.status,
    sortFn: "alphanumeric",
    enableGlobalFilter: false,
  }),
]);

const TYPE_OPTIONS = ["DocumentReference", "DiagnosticReport", "Observation", "Encounter"] as const;

interface ResourceTableProps {
  items: PatientResourceItem[];
  highlightedId?: string | null;
  onOpen: (item: PatientResourceItem) => void;
}

/** Linked FHIR records (docs/06 section 6.7): sort, type filter, text filter, dense rows. */
export function ResourceTable({ items, highlightedId, onOpen }: ResourceTableProps) {
  const [sorting, setSorting] = useState<SortingState>([{ id: "date", desc: true }]);
  const [type, setType] = useState("");
  const [text, setText] = useState("");
  const rowRefs = useRef(new Map<string, HTMLTableRowElement>());
  const ids = { type: useId(), text: useId() };

  // Stable inputs: a new filters array on every render would recompute the row models.
  const columnFilters = useMemo(() => (type ? [{ id: "type", value: type }] : []), [type]);
  const table = useTable({
    features,
    columns,
    data: items,
    state: { sorting, globalFilter: text, columnFilters },
    onSortingChange: setSorting,
    globalFilterFn: "includesString",
  });

  // The parent remounts this table for each evidence click, so filters start empty and
  // the cited row is always visible; this effect only moves the viewport and focus.
  useEffect(() => {
    if (!highlightedId) return;
    const row = rowRefs.current.get(highlightedId);
    // Not every environment implements scrollIntoView (jsdom, some embedded views).
    const scrollable = row as Partial<Pick<HTMLElement, "scrollIntoView">> | undefined;
    scrollable?.scrollIntoView?.({ block: "center", behavior: "smooth" });
    row?.querySelector<HTMLButtonElement>("button")?.focus({ preventScroll: true });
  }, [highlightedId]);

  if (items.length === 0) {
    return (
      <EmptyState
        headingLevel="h3"
        title={copy.records.emptyTitle}
        description={copy.records.emptyBody}
      />
    );
  }

  const rows = table.getRowModel().rows;
  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-end gap-2">
        <div className="flex flex-col gap-1">
          <label htmlFor={ids.type} className="text-meta text-muted-foreground">
            {copy.records.typeFilter}
          </label>
          <select
            id={ids.type}
            value={type}
            onChange={(event) => {
              setType(event.target.value);
            }}
            className="h-8 rounded-lg border border-input bg-card px-2 text-small focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/25 focus-visible:outline-none"
          >
            <option value="">{copy.records.allTypes}</option>
            {TYPE_OPTIONS.map((option) => (
              <option key={option} value={option}>
                {copy.resourceLabels[option]}
              </option>
            ))}
          </select>
        </div>
        <div className="flex min-w-48 flex-1 flex-col gap-1">
          <label htmlFor={ids.text} className="text-meta text-muted-foreground">
            {copy.records.filterLabel}
          </label>
          <Input
            id={ids.text}
            value={text}
            onChange={(event) => {
              setText(event.target.value);
            }}
            placeholder={copy.records.filterPlaceholder}
            className="h-8"
          />
        </div>
      </div>
      <div className="rounded-lg border">
        <Table aria-label={copy.records.label} className="text-small">
          <TableHeader className="sticky top-0 z-10 bg-muted">
            {table.getHeaderGroups().map((group) => (
              <TableRow key={group.id} className="h-9 hover:bg-transparent">
                {group.headers.map((header) => {
                  const sorted = header.column.getIsSorted();
                  const label = String(header.column.columnDef.header);
                  const Icon =
                    sorted === "asc"
                      ? ArrowUpIcon
                      : sorted === "desc"
                        ? ArrowDownIcon
                        : ArrowUpDownIcon;
                  return (
                    <TableHead
                      key={header.id}
                      aria-sort={
                        sorted === "asc" ? "ascending" : sorted === "desc" ? "descending" : "none"
                      }
                      className={cn(header.id === "date" && "w-28", header.id === "type" && "w-40")}
                    >
                      <button
                        type="button"
                        onClick={header.column.getToggleSortingHandler()}
                        aria-label={copy.records.sortBy(label)}
                        className="-ml-1 inline-flex h-8 items-center gap-1 rounded-md px-1 text-meta text-muted-foreground hover:text-foreground focus-visible:outline-2 focus-visible:outline-ring"
                      >
                        {label}
                        <Icon aria-hidden className="size-3.5" />
                      </button>
                    </TableHead>
                  );
                })}
              </TableRow>
            ))}
          </TableHeader>
          <TableBody>
            {rows.length === 0 ? (
              <TableRow>
                <TableCell colSpan={4} className="py-6 text-center text-muted-foreground">
                  {copy.records.noMatch}
                </TableCell>
              </TableRow>
            ) : (
              rows.map((row) => {
                const item = row.original;
                return (
                  <TableRow
                    key={item.resource_id}
                    ref={(element) => {
                      if (element) rowRefs.current.set(item.resource_id, element);
                      else rowRefs.current.delete(item.resource_id);
                    }}
                    data-highlighted={highlightedId === item.resource_id || undefined}
                    onClick={() => {
                      onOpen(item);
                    }}
                    className="h-10 cursor-pointer transition-colors duration-1000 data-highlighted:bg-accent data-highlighted:duration-0"
                  >
                    <TableCell>
                      <ResourceTypeBadge type={item.resource_type} />
                    </TableCell>
                    <TableCell className="whitespace-nowrap tabular-nums">
                      {item.date ? (
                        <time dateTime={item.date}>{formatDate(item.date)}</time>
                      ) : (
                        <span className="text-muted-foreground">{copy.ai.undated}</span>
                      )}
                    </TableCell>
                    <TableCell className="w-full max-w-0">
                      <button
                        type="button"
                        aria-label={copy.records.open(item.title)}
                        onClick={(event) => {
                          event.stopPropagation();
                          onOpen(item);
                        }}
                        className="block max-w-full truncate rounded-sm text-left font-medium hover:underline focus-visible:outline-2 focus-visible:outline-ring"
                      >
                        {item.title}
                      </button>
                      {item.summary_line && item.summary_line !== item.title ? (
                        <span className="block truncate text-meta text-muted-foreground">
                          {item.summary_line}
                        </span>
                      ) : null}
                    </TableCell>
                    <TableCell className="whitespace-nowrap">
                      <span
                        className={cn(
                          "text-meta",
                          item.is_valid ? "text-muted-foreground" : "text-destructive",
                        )}
                      >
                        {item.is_valid ? copy.records.valid : copy.records.invalid}
                      </span>
                    </TableCell>
                  </TableRow>
                );
              })
            )}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}
