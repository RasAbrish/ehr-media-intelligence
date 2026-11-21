import { useQuery } from "@tanstack/react-query";
import { useNavigate, useSearch } from "@tanstack/react-router";
import { useCallback, useEffect, useRef, useState } from "react";

import { EmptyState } from "@/components/common/EmptyState";
import { ErrorState } from "@/components/common/ErrorState";
import { IndexEmptyNotice } from "@/components/common/IndexEmptyNotice";
import { Button } from "@/components/ui/button";
import { PatientDrawer } from "@/features/patients/PatientDrawer";
import { searchQuery } from "@/features/search/api";
import { FilterBar } from "@/features/search/FilterBar";
import { activeFilterCount, type FilterValue } from "@/features/search/filters";
import { ResultList, type ResultListHandle } from "@/features/search/ResultList";
import { ResultSkeletons } from "@/features/search/ResultSkeletons";
import { QUERY_MIN, type SearchResult } from "@/features/search/schemas";
import { SearchInput } from "@/features/search/SearchInput";
import { copy } from "@/lib/copy";
import { ApiError } from "@/lib/problem";
import { modalOpen } from "@/lib/modal";
import { readyQuery } from "@/lib/system-api";

const DEBOUNCE_MS = 300;
const DEFAULT_RETRY_S = 60;

function isTypingTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  return target.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName);
}

/** Search screen (docs/06 sections 7.1 and 8.3): URL state, debounced live results, drawer. */
export function SearchPage() {
  const search = useSearch({ from: "/" });
  const navigate = useNavigate({ from: "/" });
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<ResultListHandle>(null);
  const openerRef = useRef<HTMLElement | null>(null);

  const urlQuery = search.q ?? "";
  const [draft, setDraft] = useState(urlQuery);
  const [seenUrl, setSeenUrl] = useState(urlQuery);
  const [lastPushed, setLastPushed] = useState(urlQuery);
  const timer = useRef<number | undefined>(undefined);

  // URL → draft when the URL changed from outside (back button, link). Adjusting state
  // during render is React's pattern for this; our own debounced pushes are skipped.
  if (urlQuery !== seenUrl) {
    setSeenUrl(urlQuery);
    if (urlQuery !== lastPushed) setDraft(urlQuery);
  }

  const pushQuery = useCallback(
    (value: string, replace: boolean) => {
      const next = value.trim();
      setLastPushed(next);
      void navigate({ search: (prev) => ({ ...prev, q: next || undefined }), replace });
    },
    [navigate],
  );

  // Draft → URL after 300 ms without typing; replace, so typing does not fill the history.
  const onDraftChange = (value: string) => {
    setDraft(value);
    window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => {
      pushQuery(value, true);
    }, DEBOUNCE_MS);
  };

  useEffect(
    () => () => {
      window.clearTimeout(timer.current);
    },
    [],
  );

  // "/" and Ctrl/Cmd+K focus the search field from anywhere (docs/06 section 8.4).
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (modalOpen()) return; // the drawer and dialogs keep focus while open
      const commandK = (event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k";
      if (commandK || (event.key === "/" && !isTypingTarget(event.target))) {
        event.preventDefault();
        inputRef.current?.focus();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("keydown", onKey);
    };
  }, []);

  const filters: FilterValue = {
    types: search.type ?? [],
    from: search.from ?? null,
    to: search.to ?? null,
  };
  const params = { q: urlQuery, types: filters.types, from: filters.from, to: filters.to };
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

  const runExample = (example: string) => {
    window.clearTimeout(timer.current);
    setDraft(example);
    pushQuery(example, false);
  };

  const [openedResource, setOpenedResource] = useState<string | null>(null);
  const openPatient = useCallback(
    (result: SearchResult, element: HTMLElement) => {
      openerRef.current = element;
      setOpenedResource(result.resource.resource_id);
      void navigate({ search: (prev) => ({ ...prev, patient: result.patient.patient_key }) });
    },
    [navigate],
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
      ? copy.search.meta(data.total, Math.round(data.took_ms), data.mode)
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
        inputRef={inputRef}
        onArrowDown={() => listRef.current?.focusFirst()}
      />
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
          <div className="flex items-baseline justify-between gap-4 text-meta text-muted-foreground">
            <p>{copy.search.meta(data.total, Math.round(data.took_ms), data.mode)}</p>
            <p className="hidden md:block">{copy.search.ranked}</p>
          </div>
          {data.results.length ? (
            <ResultList
              results={data.results}
              onOpen={openPatient}
              selectedId={search.patient ? openedResource : null}
              handleRef={listRef}
            />
          ) : (
            <EmptyState
              title={copy.search.noResultsTitle}
              description={copy.search.noResultsBody}
              action={
                hasFilters ? (
                  <Button
                    variant="outline"
                    onClick={() => {
                      setFilters({ types: [], from: null, to: null });
                    }}
                  >
                    {copy.filters.clear}
                  </Button>
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
