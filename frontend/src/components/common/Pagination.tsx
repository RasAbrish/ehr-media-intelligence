import { useEffect, useId } from "react";

import { Button } from "@/components/ui/button";
import { copy } from "@/lib/copy";
import { PAGE_SIZES } from "@/lib/url-params";

interface PaginationProps {
  page: number;
  pageSize: number;
  total: number;
  totalPages: number;
  onPage: (page: number) => void;
  /** Omit to hide the page size select (narrow surfaces). */
  onPageSize?: (size: number) => void;
}

/** "Rows 1 to 25 of 60", previous and next, page size (docs/06 section 6.8). */
export function Pagination({
  page,
  pageSize,
  total,
  totalPages,
  onPage,
  onPageSize,
}: PaginationProps) {
  const sizeId = useId();
  useEffect(() => {
    if (page > totalPages) onPage(totalPages); // an old link, or the data shrank
  }, [page, totalPages, onPage]);
  const first = Math.min((page - 1) * pageSize + 1, total);
  const last = Math.min(page * pageSize, total);
  return (
    <div className="flex flex-wrap items-center justify-between gap-2 text-meta text-muted-foreground">
      <p role="status" className="tabular-nums">
        {copy.table.range(first, last, total)}
      </p>
      <div className="flex flex-wrap items-center gap-2">
        {onPageSize ? (
          <>
            <label htmlFor={sizeId}>{copy.table.pageSize}</label>
            <select
              id={sizeId}
              value={pageSize}
              onChange={(event) => {
                onPageSize(Number(event.target.value));
              }}
              className="h-8 rounded-lg border border-input bg-card px-2 text-foreground max-md:h-11"
            >
              {PAGE_SIZES.map((size) => (
                <option key={size} value={size}>
                  {size}
                </option>
              ))}
            </select>
          </>
        ) : null}
        <Button
          variant="outline"
          className="h-8 max-md:h-11"
          disabled={page <= 1}
          onClick={() => {
            onPage(page - 1);
          }}
        >
          {copy.table.previous}
        </Button>
        <Button
          variant="outline"
          className="h-8 max-md:h-11"
          disabled={page >= totalPages}
          onClick={() => {
            onPage(page + 1);
          }}
        >
          {copy.table.next}
        </Button>
      </div>
    </div>
  );
}
