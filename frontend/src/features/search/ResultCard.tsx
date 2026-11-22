import { TriangleAlertIcon } from "lucide-react";
import { useEffect, useRef, type FocusEvent, type KeyboardEvent, type Ref } from "react";

import { AiBadge } from "@/components/common/AiBadge";
import { CopyButton } from "@/components/common/CopyButton";
import { Highlight } from "@/components/common/Highlight";
import { ResourceTypeBadge } from "@/components/common/ResourceTypeBadge";
import { ScoreMeter } from "@/components/common/ScoreMeter";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import type { SearchResult } from "@/features/search/schemas";
import { WhyThisResult } from "@/features/search/WhyThisResult";
import { copy } from "@/lib/copy";
import { ageSex, formatDate } from "@/lib/format";
import { cn } from "@/lib/utils";

/** A passing mouse does not prefetch; patient routes are limited to 120 requests a minute. */
const HOVER_INTENT_MS = 120;

interface ResultCardProps {
  result: SearchResult;
  onOpen: (result: SearchResult, element: HTMLElement) => void;
  selected?: boolean;
  /** Newest order: no relevance to show. */
  byDate?: boolean;
  buttonRef?: Ref<HTMLButtonElement>;
  tabIndex?: number;
  /** Called on focus and after a short hover (docs/06 section 8.5). */
  onPrefetch?: (patientKey: string) => void;
  onFocus?: (event: FocusEvent) => void;
  onKeyDown?: (event: KeyboardEvent) => void;
}

/**
 * One search result (docs/06 section 6.5). The whole card opens the patient; the copy and
 * "why this result" controls sit beside the card button, never inside it.
 * Reading order: patient, record type and date, finding, AI line, score.
 */
export function ResultCard({
  result,
  onOpen,
  selected,
  byDate = false,
  buttonRef,
  tabIndex,
  onFocus,
  onKeyDown,
  onPrefetch,
}: ResultCardProps) {
  const hoverTimer = useRef<number | undefined>(undefined);
  useEffect(
    () => () => {
      window.clearTimeout(hoverTimer.current);
    },
    [],
  );
  const { patient, resource } = result;
  const who = ageSex(patient.age, patient.gender);
  const date = formatDate(resource.date);
  const id = `result-${result.rank}`;
  const titleId = `${id}-title`;
  // Screen readers hear the whole card from the button: type, date, title, finding,
  // AI line and score (FR-5.2, FR-5.6).
  const describedBy = [
    `${id}-meta`,
    `${id}-snippet`,
    `${id}-ai`,
    ...(byDate ? [] : [`${id}-score`]),
  ].join(" ");
  return (
    <article
      aria-labelledby={titleId}
      data-selected={selected ? "" : undefined}
      className={cn(
        "group/card relative rounded-xl border bg-card transition-colors hover:bg-accent/40",
        "has-[[data-card-button]:focus-visible]:border-ring has-[[data-card-button]:focus-visible]:shadow-[inset_3px_0_0_var(--primary)]",
        selected && "border-ring shadow-[inset_3px_0_0_var(--primary)]",
      )}
    >
      <button
        type="button"
        data-card-button
        ref={buttonRef}
        tabIndex={tabIndex}
        onFocus={(event) => {
          onFocus?.(event);
          onPrefetch?.(patient.patient_key);
        }}
        onKeyDown={onKeyDown}
        onClick={(event) => {
          onOpen(result, event.currentTarget);
        }}
        aria-label={copy.card.open(patient.display_name, resource.title)}
        aria-describedby={describedBy}
        className="absolute inset-0 rounded-xl outline-none"
      />
      {/* Mouse convenience: a click anywhere opens the patient unless the user selected
          text to copy. Keyboard and screen reader users use the card button above. */}
      {/* eslint-disable-next-line jsx-a11y/click-events-have-key-events, jsx-a11y/no-static-element-interactions -- see comment above */}
      <div
        className="relative flex cursor-pointer flex-col gap-1.5 p-3 md:p-4"
        onMouseEnter={() => {
          window.clearTimeout(hoverTimer.current);
          hoverTimer.current = window.setTimeout(() => {
            onPrefetch?.(patient.patient_key);
          }, HOVER_INTENT_MS);
        }}
        onMouseLeave={() => {
          window.clearTimeout(hoverTimer.current);
        }}
        onClick={(event) => {
          if (window.getSelection()?.toString()) return;
          if ((event.target as HTMLElement).closest("button, a, [role='dialog']")) return;
          const button =
            event.currentTarget.parentElement?.querySelector<HTMLElement>("[data-card-button]");
          if (button) onOpen(result, button);
        }}
      >
        <div className="flex items-start gap-3">
          <div className="flex min-w-0 flex-1 flex-wrap items-center gap-x-2 gap-y-0.5">
            <h2 id={titleId} className="text-body font-medium">
              {patient.display_name}
            </h2>
            <span className="inline-flex items-center gap-0.5 font-mono text-mono text-muted-foreground">
              {copy.card.mrn(patient.mrn)}
              <span className="opacity-100 md:opacity-0 md:group-focus-within/card:opacity-100 md:group-hover/card:opacity-100">
                <CopyButton
                  value={patient.mrn}
                  label={copy.card.copyMrn}
                  confirmation={copy.card.copied(patient.mrn)}
                />
              </span>
            </span>
            <span className="text-meta text-muted-foreground" title={who.long}>
              <span aria-hidden>{who.short}</span>
              <span className="sr-only">{who.long}</span>
            </span>
            {patient.identity_conflict ? (
              <span
                className="inline-flex h-5.5 items-center gap-1 rounded-sm border border-warning/40 bg-warning/15 px-1.5 text-meta text-warning-foreground dark:text-warning"
                title={copy.card.conflictHint}
              >
                <TriangleAlertIcon aria-hidden className="size-3.5" />
                {copy.card.conflict}
              </span>
            ) : null}
          </div>
          <div className="flex shrink-0 items-center gap-0.5">
            {byDate ? null : <ScoreMeter id={`${id}-score`} score={result.score} compact />}
            <WhyThisResult result={result} byDate={byDate} />
          </div>
        </div>
        <div id={`${id}-meta`} className="flex min-w-0 items-center gap-2">
          <ResourceTypeBadge type={resource.resource_type} />
          {date ? (
            <>
              <time
                dateTime={resource.date ?? undefined}
                className="shrink-0 text-meta text-muted-foreground tabular-nums"
              >
                {date}
              </time>
              <span aria-hidden className="text-muted-foreground">
                ·
              </span>
            </>
          ) : null}
          {/* Not a tab stop: the card button's name already carries the full title. */}
          <Tooltip>
            <TooltipTrigger render={<span />} className="truncate text-small text-foreground">
              {resource.title}
            </TooltipTrigger>
            <TooltipContent>{resource.title}</TooltipContent>
          </Tooltip>
        </div>
        <p
          id={`${id}-snippet`}
          className="line-clamp-3 text-small text-muted-foreground md:line-clamp-2"
        >
          <Highlight text={result.snippet} ranges={result.highlights} />
        </p>
        <p id={`${id}-ai`} className="flex min-w-0 items-center gap-2 text-small">
          {result.summary_snippet ? (
            <>
              <AiBadge />
              <span className="truncate">{result.summary_snippet}</span>
            </>
          ) : (
            <span className="truncate text-muted-foreground italic">{copy.card.noSummary}</span>
          )}
        </p>
      </div>
    </article>
  );
}
