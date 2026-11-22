import { useQuery } from "@tanstack/react-query";
import { useNavigate, useSearch } from "@tanstack/react-router";
import { useCallback, useId, useRef } from "react";

import { EmptyState } from "@/components/common/EmptyState";
import { ErrorState } from "@/components/common/ErrorState";
import { IndexEmptyNotice } from "@/components/common/IndexEmptyNotice";
import { PageHeader } from "@/components/common/PageHeader";
import { Pagination } from "@/components/common/Pagination";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { directoryQuery } from "@/features/patients/api";
import type { DirectoryPageParams } from "@/features/patients/directory-params";
import { DirectoryTable } from "@/features/patients/DirectoryTable";
import { PatientDrawer } from "@/features/patients/PatientDrawer";
import { useUrlText } from "@/hooks/useUrlText";
import { copy } from "@/lib/copy";

const DEFAULT_SIZE = 25;

/** Patient directory (FR-5.7): server-side search, sort and paging, all in the URL. */
export function PatientsPage() {
  const search = useSearch({ from: "/patients" });
  const navigate = useNavigate({ from: "/patients" });
  const openerRef = useRef<HTMLElement | null>(null);
  const ids = { search: useId(), conflict: useId() };

  const writeQuery = useCallback(
    (value: string, replace: boolean) => {
      void navigate({
        search: (prev) => ({ ...prev, q: value || undefined, page: undefined }),
        replace,
      });
    },
    [navigate],
  );
  const text = useUrlText(search.q ?? "", writeQuery);

  const change = (next: DirectoryPageParams) => {
    void navigate({ search: (prev) => ({ ...prev, page: undefined, ...next }), replace: true });
  };

  const sort = search.sort ?? "last_activity";
  const order = search.order ?? "desc";
  const query = useQuery(
    directoryQuery({
      q: search.q ?? "",
      sort,
      order,
      page: search.page ?? 1,
      size: search.size ?? DEFAULT_SIZE,
      conflictOnly: search.conflict ?? false,
    }),
  );
  const filtered = Boolean(search.q) || Boolean(search.conflict);
  const data = query.data;

  return (
    <section className="flex flex-col gap-4">
      <PageHeader title={copy.patients.title} description={copy.patients.body} />
      <div className="flex flex-wrap items-end gap-3">
        <div className="flex min-w-60 flex-1 flex-col gap-1">
          <label htmlFor={ids.search} className="text-meta text-muted-foreground">
            {copy.directory.search}
          </label>
          <Input
            id={ids.search}
            type="search"
            data-page-search
            maxLength={100}
            value={text.draft}
            placeholder={copy.directory.placeholder}
            onChange={(event) => {
              text.change(event.target.value);
            }}
            className="h-9 bg-card max-md:h-11"
          />
        </div>
        <label
          htmlFor={ids.conflict}
          className="flex h-9 items-center gap-2 text-small max-md:h-11"
        >
          <Checkbox
            id={ids.conflict}
            checked={search.conflict ?? false}
            onCheckedChange={(checked) => {
              change({ conflict: checked ? true : undefined });
            }}
          />
          {copy.directory.conflictOnly}
        </label>
      </div>

      {query.isError ? (
        <ErrorState
          title={copy.errors.directoryTitle}
          error={query.error}
          onRetry={() => void query.refetch()}
        />
      ) : !data ? (
        <div role="status" aria-label={copy.directory.loading} className="flex flex-col gap-1">
          {Array.from({ length: 8 }, (_, index) => (
            <Skeleton key={index} className="h-10 w-full" />
          ))}
        </div>
      ) : data.total === 0 ? (
        filtered ? (
          <EmptyState title={copy.directory.noMatch} description={copy.directory.noMatchBody} />
        ) : (
          <IndexEmptyNotice />
        )
      ) : (
        <>
          <DirectoryTable
            items={data.items}
            sort={sort}
            order={order}
            onSort={(nextSort, nextOrder) => {
              change({ sort: nextSort, order: nextOrder });
            }}
            onOpen={(key, opener) => {
              openerRef.current = opener;
              void navigate({ search: (prev) => ({ ...prev, patient: key }) });
            }}
          />
          <Pagination
            page={data.page}
            pageSize={search.size ?? data.page_size}
            total={data.total}
            totalPages={data.total_pages}
            onPage={(page) => {
              change({ page });
            }}
            onPageSize={(size) => {
              change({ size });
            }}
          />
        </>
      )}

      <PatientDrawer
        patientKey={search.patient ?? null}
        returnFocusRef={openerRef}
        onClose={() => {
          void navigate({ search: (prev) => ({ ...prev, patient: undefined }) });
        }}
      />
    </section>
  );
}
