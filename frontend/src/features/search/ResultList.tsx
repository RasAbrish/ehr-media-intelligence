import { useImperativeHandle, type Ref } from "react";

import { ResultCard } from "@/features/search/ResultCard";
import type { SearchResult } from "@/features/search/schemas";
import { useRovingFocus } from "@/hooks/useRovingFocus";
import { copy } from "@/lib/copy";

export interface ResultListHandle {
  focusFirst: () => void;
}

interface ResultListProps {
  results: SearchResult[];
  onOpen: (result: SearchResult, element: HTMLElement) => void;
  /** The record whose card opened the drawer (one card, not every card of that patient). */
  selectedId?: string | null;
  onPrefetch?: (patientKey: string) => void;
  handleRef?: Ref<ResultListHandle>;
}

/** Results as a list of card buttons with one tab stop and arrow-key navigation. */
export function ResultList({
  results,
  onOpen,
  selectedId,
  handleRef,
  onPrefetch,
}: ResultListProps) {
  const roving = useRovingFocus(results.length);
  useImperativeHandle(
    handleRef,
    () => ({
      focusFirst: () => {
        roving.focus(0);
      },
    }),
    [roving],
  );
  return (
    <ul aria-label={copy.search.resultsLabel} className="flex flex-col gap-2">
      {results.map((result, index) => {
        const item = roving.itemProps(index);
        return (
          <li key={result.resource.resource_id}>
            <ResultCard
              result={result}
              onOpen={onOpen}
              {...(onPrefetch ? { onPrefetch } : {})}
              selected={selectedId === result.resource.resource_id}
              buttonRef={item.ref}
              tabIndex={item.tabIndex}
              onFocus={item.onFocus}
              onKeyDown={roving.onKeyDown}
            />
          </li>
        );
      })}
    </ul>
  );
}
