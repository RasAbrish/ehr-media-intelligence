import {
  createColumnHelper,
  rowSortingFeature,
  tableFeatures,
  useTable,
  type SortingState,
  type TableOptions,
} from "@tanstack/react-table";
import { ArrowDownIcon, ArrowUpDownIcon, ArrowUpIcon } from "lucide-react";

import { TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { copy } from "@/lib/copy";
import { cn } from "@/lib/utils";

// Sorting and paging happen on the server, so no client row models are registered.
const features = tableFeatures({ rowSortingFeature });
const NO_SORTING: SortingState = [];

export function serverColumns<T extends object>() {
  return createColumnHelper<typeof features, T>();
}

interface DataTableProps<T extends object> {
  label: string;
  columns: TableOptions<typeof features, T>["columns"];
  rows: T[];
  rowId: (row: T) => string;
  /** Column ids that take a whole line in the card layout. The first column always does. */
  wide?: readonly string[];
  /** Column ids that are right aligned with tabular numbers. */
  numeric?: readonly string[];
  sorting?: SortingState;
  onSortingChange?: (next: SortingState) => void;
  onRowClick?: (row: T, element: HTMLTableRowElement) => void;
}

/**
 * Dense server-side table (docs/06 section 6.8): header 36, rows 40, sort buttons with aria-sort.
 * In a container under 60rem each row is a labeled card. The roles are explicit because
 * changing `display` drops the implicit table semantics in some browsers.
 */
export function DataTable<T extends object>({
  label,
  columns,
  rows,
  rowId,
  numeric = [],
  wide = [],
  sorting = NO_SORTING,
  onSortingChange,
  onRowClick,
}: DataTableProps<T>) {
  const table = useTable({
    features,
    columns,
    data: rows,
    getRowId: rowId,
    state: { sorting },
    manualSorting: true,
    enableSorting: onSortingChange !== undefined,
    enableSortingRemoval: false,
    sortDescFirst: false,
    onSortingChange: (updater) => {
      onSortingChange?.(typeof updater === "function" ? updater(sorting) : updater);
    },
  });
  const anySortable = table.getAllLeafColumns().some((column) => column.getCanSort());
  return (
    // Rows stack before they overflow. Anything wider still scrolls here, by keyboard too.
    <div
      role="region"
      aria-label={copy.table.region(label)}
      // eslint-disable-next-line jsx-a11y/no-noninteractive-tabindex -- keyboard scrolling (axe scrollable-region-focusable)
      tabIndex={0}
      className="@container/data-table relative overflow-x-auto rounded-lg border bg-card focus-visible:outline-2 focus-visible:outline-ring"
    >
      <table role="table" aria-label={label} className="w-full text-small stacked:block">
        <TableHeader
          role="rowgroup"
          className={cn("bg-muted stacked:block", !anySortable && "stacked:sr-only")}
        >
          {table.getHeaderGroups().map((group) => (
            <TableRow
              key={group.id}
              role="row"
              className="h-9 hover:bg-transparent stacked:flex stacked:h-auto stacked:flex-wrap stacked:gap-x-2 stacked:px-2 stacked:py-1"
            >
              {group.headers.map((header) => {
                const sorted = header.column.getIsSorted();
                const name = String(header.column.columnDef.header);
                const Icon =
                  sorted === "asc"
                    ? ArrowUpIcon
                    : sorted === "desc"
                      ? ArrowDownIcon
                      : ArrowUpDownIcon;
                const sortable = header.column.getCanSort();
                return (
                  <TableHead
                    key={header.id}
                    role="columnheader"
                    {...(sortable
                      ? {
                          "aria-sort":
                            sorted === "asc"
                              ? "ascending"
                              : sorted === "desc"
                                ? "descending"
                                : "none",
                        }
                      : {})}
                    className={cn(
                      "h-9 text-meta whitespace-normal text-muted-foreground stacked:h-auto stacked:p-0 stacked:text-left",
                      !sortable && "stacked:sr-only",
                      numeric.includes(header.id) && "text-right",
                    )}
                  >
                    {sortable ? (
                      <button
                        type="button"
                        onClick={header.column.getToggleSortingHandler()}
                        aria-label={copy.records.sortBy(name)}
                        className="-ml-1 inline-flex min-h-8 items-center gap-1 rounded-md px-1 text-left hover:text-foreground focus-visible:outline-2 focus-visible:outline-ring max-md:min-h-11 max-md:min-w-11 stacked:ml-0"
                      >
                        {name}
                        <Icon aria-hidden className="size-3.5" />
                      </button>
                    ) : (
                      name
                    )}
                  </TableHead>
                );
              })}
            </TableRow>
          ))}
        </TableHeader>
        <TableBody role="rowgroup" className="stacked:block">
          {table.getRowModel().rows.map((row) => (
            <TableRow
              key={row.id}
              role="row"
              className={cn(
                "h-10 stacked:grid stacked:h-auto stacked:grid-cols-[repeat(auto-fill,minmax(7.5rem,1fr))] stacked:gap-x-3 stacked:gap-y-2 stacked:p-3",
                onRowClick && "cursor-pointer",
              )}
              onClick={(event) => {
                // A drag that selects text to copy is not a click on the row.
                if (window.getSelection()?.toString()) return;
                onRowClick?.(row.original, event.currentTarget);
              }}
            >
              {row.getAllCells().map((cell, index) => (
                <TableCell
                  key={cell.id}
                  role="cell"
                  data-label={String(cell.column.columnDef.header)}
                  className={cn(
                    "py-1 whitespace-normal stacked:block stacked:min-w-0 stacked:p-0 stacked:text-left stacked:wrap-anywhere stacked:empty:hidden",
                    // The label is generated content, so the cell's text stays the value alone.
                    index === 0
                      ? "stacked:col-span-full"
                      : "stacked:before:block stacked:before:text-meta stacked:before:text-muted-foreground stacked:before:content-[attr(data-label)]",
                    wide.includes(cell.column.id) && "stacked:col-span-full",
                    numeric.includes(cell.column.id) && "text-right tabular-nums",
                  )}
                >
                  <table.FlexRender cell={cell} />
                </TableCell>
              ))}
            </TableRow>
          ))}
        </TableBody>
      </table>
    </div>
  );
}
