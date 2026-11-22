import { InfoIcon } from "lucide-react";

import { matchedTerms } from "@/components/common/Highlight";
import { Popover, PopoverContent, PopoverTitle, PopoverTrigger } from "@/components/ui/popover";
import type { SearchResult } from "@/features/search/schemas";
import { copy } from "@/lib/copy";
import { formatDate, formatScore } from "@/lib/format";

/** Search transparency popover (docs/06 section 12.3). */
export function WhyThisResult({
  result,
  byDate = false,
}: {
  result: SearchResult;
  /** Newest order: similarity was not computed. */
  byDate?: boolean;
}) {
  const terms = matchedTerms(result.snippet, result.highlights);
  const date = formatDate(result.resource.date);
  const record = [copy.resourceLabels[result.resource.resource_type], date]
    .filter(Boolean)
    .join(" · ");
  return (
    <Popover>
      <PopoverTrigger
        aria-label={copy.why.trigger}
        onClick={(event) => {
          event.stopPropagation();
        }}
        className="inline-flex size-8 items-center justify-center rounded-md text-muted-foreground hover:bg-muted hover:text-foreground focus-visible:outline-2 focus-visible:outline-ring max-md:size-11"
      >
        <InfoIcon aria-hidden className="size-4" />
      </PopoverTrigger>
      <PopoverContent
        align="end"
        className="w-72 p-3"
        onClick={(event) => {
          event.stopPropagation();
        }}
      >
        <PopoverTitle className="text-heading">{copy.why.title}</PopoverTitle>
        <dl className="mt-2 grid grid-cols-[auto_1fr] gap-x-3 gap-y-1.5 text-small">
          <dt className="text-muted-foreground">{copy.why.match}</dt>
          <dd>{copy.why.matchTypes[result.match_type]}</dd>
          {byDate ? null : (
            <>
              <dt className="text-muted-foreground">{copy.why.similarity}</dt>
              <dd className="font-mono text-mono tabular-nums">
                {formatScore(result.semantic_score)}
              </dd>
            </>
          )}
          <dt className="text-muted-foreground">{copy.why.terms}</dt>
          <dd>{terms.length ? terms.join(", ") : copy.why.noTerms}</dd>
          <dt className="text-muted-foreground">{copy.why.record}</dt>
          <dd>{record}</dd>
        </dl>
        {result.resource.resource_type === "ClinicalSummary" ? (
          <p className="mt-2 text-small text-ai">{copy.why.summaryHit}</p>
        ) : null}
      </PopoverContent>
    </Popover>
  );
}
