import { noop, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate, useSearch } from "@tanstack/react-router";
import { useCallback, useRef, useState } from "react";

import { EmptyState } from "@/components/common/EmptyState";
import { ErrorState } from "@/components/common/ErrorState";
import { IndexEmptyNotice } from "@/components/common/IndexEmptyNotice";
import { OnboardingTip } from "@/components/common/OnboardingTip";
import { Button } from "@/components/ui/button";
import { patientQuery, summaryQuery } from "@/features/patients/api";
import { loadDrawerBody } from "@/features/patients/drawer-chunk";
import { PatientDrawer } from "@/features/patients/PatientDrawer";
import { searchQuery } from "@/features/search/api";
import { FilterBar } from "@/features/search/FilterBar";
import { activeFilterCount, type FilterValue } from "@/features/search/filters";
import { ResultList, type ResultListHandle } from "@/features/search/ResultList";
import { ResultSkeletons } from "@/features/search/ResultSkeletons";
import { QUERY_MIN, type SearchResult } from "@/features/search/schemas";
import { SearchInput } from "@/features/search/SearchInput";
import { SortSelect } from "@/features/search/SortSelect";
import { useUrlText } from "@/hooks/useUrlText";
import type { SearchSort } from "@/lib/contract-enums";
import { copy } from "@/lib/copy";
import { ApiError } from "@/lib/problem";
import { readyQuery } from "@/lib/system-api";

const DEFAULT_RETRY_S = 60;

/** Search screen (docs/06 sections 7.1 and 8.3): URL state, debounced live results, drawer. */
export function SearchPage() {
  const search = useSearch({ from: "/_app/" });
  const navigate = useNavigate({ from: "/" });
  const listRef = useRef<ResultListHandle>(null);
  const openerRef = useRef<HTMLElement | null>(null);

  const urlQuery = search.q ?? "";
  const writeQuery = useCallback(
    (value: string, replace: boolean) => {
      void navigate({ search: (prev) => ({ ...prev, q: value || undefined }), replace });
    },
    [navigate],
  );
  const { draft, change: onDraftChange, choose: runExample } = useUrlText(urlQuery, writeQuery);

  const filters: FilterValue = {
    types: search.type ?? [],
    from: search.from ?? null,
    to: search.to ?? null,
  };
  const params = {
    q: urlQuery,
    types: filters.types,
    from: filters.from,
    to: filters.to,
    sort: search.sort,
  };
  const results = useQuery(searchQuery(params));
  const ready = useQuery(readyQuery());
  const active = urlQuery.length >= QUERY_MIN;

  const setFilters = (next: FilterValue) =>
    void navigate({
      search: (prev) => ({
        ...prev,
        type: next.types.length ? next.types : undefined,
        from: next.from ?? undefined,
        to: next.to ?? undefined,
      }),
      replace: true,
    });

  const setSort = (next: SearchSort) =>
    void navigate({
      search: (prev) => ({ ...prev, sort: next === "newest" ? next : undefined }),
      replace: true,
    });

  const [openedResource, setOpenedResource] = useState<string | null>(null);
  const openPatient = useCallback(
    (result: SearchResult, element: HTMLElement) => {
      openerRef.current = element;
      setOpenedResource(result.resource.resource_id);
      void navigate({ search: (prev) => ({ ...prev, patient: result.patient.patient_key }) });
    },
    [navigate],
  );

  const queryClient = useQueryClient();
  const prefetchPatient = useCallback(
    (key: string) => {
      loadDrawerBody().catch(noop); // opening the drawer reports a failed load
      queryClient.query(patientQuery(key)).catch(noop); // the drawer shows any error itself
      queryClient.query(summaryQuery(key)).catch(noop); // the drawer shows any error itself
    },
    [queryClient],
  );

  const closePatient = useCallback(() => {
    void navigate({ search: (prev) => ({ ...prev, patient: undefined }) });
  }, [navigate]);

  const indexEmpty =
    (results.error instanceof ApiError && results.error.code === "search_index_empty") ||
    ready.data?.counts.chunks === 0;
  const data = results.data;
  const hasFilters = activeFilterCount(filters) > 0;
  // A 429 is retried once after Retry-After (docs/04 section 11.2); say so while waiting.
  const waitingOn429 =
    results.isFetching &&
    results.failureReason instanceof ApiError &&
    results.failureReason.status === 429;
  // One live region that is always in the page, so the first count is announced too.
  const liveText =
    active && data && !results.isFetching
      ? copy.search.meta(data.total, Math.round(data.took_ms), data.mode, data.sort)
      : "";

  return (
    <section className="flex flex-col gap-4" aria-labelledby="search-title">
      {active ? (
        <h1 id="search-title" className="sr-only">
          {copy.search.pageLabel}
        </h1>
      ) : null}
      <SearchInput
        value={draft}
        onChange={onDraftChange}
        isFetching={active && results.isFetching}
        onArrowDown={() => listRef.current?.focusFirst()}
      />
      <OnboardingTip />
      <FilterBar value={filters} onChange={setFilters} />
      <p className="sr-only" aria-live="polite" aria-atomic="true">
        {liveText}
      </p>

      {indexEmpty ? <IndexEmptyNotice /> : null}

      {!active ? (
        <div className="mt-6 flex flex-col gap-4">
          <div className="flex flex-col gap-1">
            <h1 id="search-title" className="text-display">
              {copy.search.idleTitle}
            </h1>
            <p className="max-w-[75ch] text-muted-foreground">{copy.search.idleBody}</p>
          </div>
          <ul aria-label={copy.search.examplesLabel} className="flex flex-wrap gap-2">
            {copy.search.examples.map((example) => (
              <li key={example}>
                <Button
                  variant="secondary"
                  className="h-9 rounded-full px-3.5 max-md:h-11"
                  onClick={() => {
                    runExample(example);
                  }}
                >
                  {example}
                </Button>
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {waitingOn429 ? (
        <p role="status" className="text-small text-muted-foreground">
          {copy.errors.rateLimited(
            (results.failureReason as ApiError).retryAfterSeconds ?? DEFAULT_RETRY_S,
          )}
        </p>
      ) : null}

      {active && results.isError && !indexEmpty ? (
        <ErrorState error={results.error} onRetry={() => void results.refetch()} />
      ) : null}

      {active && results.isPending && !data ? <ResultSkeletons /> : null}

      {active && data ? (
        <div className="flex flex-col gap-2">
          <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1 text-meta text-muted-foreground">
            <p>{copy.search.meta(data.total, Math.round(data.took_ms), data.mode, data.sort)}</p>
            <SortSelect value={search.sort ?? "relevance"} onChange={setSort} />
          </div>
          {data.sort === "newest" ? (
            <p className="text-meta text-muted-foreground">{copy.sort.newestNote}</p>
          ) : null}
          {data.results.length ? (
            <ResultList
              results={data.results}
              byDate={data.sort === "newest"}
              onOpen={openPatient}
              onPrefetch={prefetchPatient}
              selectedId={search.patient ? openedResource : null}
              handleRef={listRef}
            />
          ) : (
            <EmptyState
              title={data.sort === "newest" ? copy.sort.noneTitle : copy.search.noResultsTitle}
              description={data.sort === "newest" ? copy.sort.noneBody : copy.search.noResultsBody}
              action={
                data.sort === "newest" || hasFilters ? (
                  <div className="flex flex-wrap gap-2">
                    {data.sort === "newest" ? (
                      <Button
                        variant="outline"
                        className="max-md:h-11"
                        onClick={() => {
                          setSort("relevance");
                        }}
                      >
                        {copy.sort.useRelevance}
                      </Button>
                    ) : null}
                    {hasFilters ? (
                      <Button
                        variant="outline"
                        className="max-md:h-11"
                        onClick={() => {
                          setFilters({ types: [], from: null, to: null });
                        }}
                      >
                        {copy.filters.clear}
                      </Button>
                    ) : null}
                  </div>
                ) : undefined
              }
            />
          )}
        </div>
      ) : null}

      <PatientDrawer
        patientKey={search.patient ?? null}
        onClose={closePatient}
        returnFocusRef={openerRef}
      />
    </section>
  );
}
