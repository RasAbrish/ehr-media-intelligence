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
  /** Column ids that are right aligned with tabular numbers. */
  numeric?: readonly string[];
  sorting?: SortingState;
  onSortingChange?: (next: SortingState) => void;
  onRowClick?: (row: T, element: HTMLTableRowElement) => void;
}

/** Dense server-side table (docs/06 section 6.8): header 36, rows 40, sort buttons with aria-sort. */
export function DataTable<T extends object>({
  label,
  columns,
  rows,
  rowId,
  numeric = [],
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
  return (
    // A wide table scrolls inside its own region, which must be reachable by keyboard.
    <div
      role="region"
      aria-label={copy.table.region(label)}
      // eslint-disable-next-line jsx-a11y/no-noninteractive-tabindex -- keyboard scrolling (axe scrollable-region-focusable)
      tabIndex={0}
      className="overflow-x-auto rounded-lg border bg-card focus-visible:outline-2 focus-visible:outline-ring"
    >
      <table aria-label={label} className="w-full text-small">
        <TableHeader className="bg-muted">
          {table.getHeaderGroups().map((group) => (
            <TableRow key={group.id} className="h-9 hover:bg-transparent">
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
                      "text-meta text-muted-foreground",
                      numeric.includes(header.id) && "text-right",
                    )}
                  >
                    {sortable ? (
                      <button
                        type="button"
                        onClick={header.column.getToggleSortingHandler()}
                        aria-label={copy.records.sortBy(name)}
                        className="-ml-1 inline-flex h-8 items-center gap-1 rounded-md px-1 hover:text-foreground focus-visible:outline-2 focus-visible:outline-ring max-md:h-11"
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
        <TableBody>
          {table.getRowModel().rows.map((row) => (
            <TableRow
              key={row.id}
              className={cn("h-10", onRowClick && "cursor-pointer")}
              onClick={(event) => {
                // A drag that selects text to copy is not a click on the row.
                if (window.getSelection()?.toString()) return;
                onRowClick?.(row.original, event.currentTarget);
              }}
            >
              {row.getAllCells().map((cell) => (
                <TableCell
                  key={cell.id}
                  className={cn(
                    "py-1",
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
