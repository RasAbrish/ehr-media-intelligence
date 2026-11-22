import { InfoIcon } from "lucide-react";

import { Popover, PopoverContent, PopoverTitle, PopoverTrigger } from "@/components/ui/popover";
import type { ClinicalSummaryResponse } from "@/features/patients/schemas";
import { copy } from "@/lib/copy";
import { cn } from "@/lib/utils";

const STEPS = { low: 1, medium: 2, high: 3 } as const;

/** "ungrounded_removed (2)" in plain language. */
function plainNote(note: string): string {
  const code = note.split(" ")[0] ?? "";
  return code in copy.confidence.notes
    ? copy.confidence.notes[code as keyof typeof copy.confidence.notes]
    : copy.confidence.otherNote;
}

/** 3-step bar, level and score, with the rationale in words (docs/06 section 12.2). */
export function ConfidenceMeter({
  confidence,
  notes,
}: {
  confidence: ClinicalSummaryResponse["confidence"];
  notes: readonly string[];
}) {
  const level = copy.ai.confidenceLevels[confidence.level];
  const score = confidence.score.toFixed(2);
  return (
    <div className="flex flex-col gap-1">
      <div className="flex items-center gap-1">
        <div
          className="flex items-center gap-2 text-small"
          role="img"
          aria-label={copy.ai.confidenceAria(level, score)}
        >
          <span className="text-muted-foreground">{copy.ai.confidence}</span>
          <span aria-hidden className="flex items-center gap-0.5">
            {[1, 2, 3].map((step) => (
              <span
                key={step}
                className={cn(
                  "h-2.5 w-3 rounded-[1px]",
                  step <= STEPS[confidence.level] ? "bg-foreground/70" : "bg-muted-foreground/25",
                )}
              />
            ))}
          </span>
          <span aria-hidden className="font-medium">
            {level}
          </span>
          <span aria-hidden className="font-mono text-mono text-muted-foreground tabular-nums">
            {score}
          </span>
        </div>
        <Popover>
          <PopoverTrigger
            aria-label={copy.confidence.trigger}
            className="inline-flex size-8 items-center justify-center rounded-md text-muted-foreground hover:bg-muted hover:text-foreground focus-visible:outline-2 focus-visible:outline-ring max-md:size-11"
          >
            <InfoIcon aria-hidden className="size-4" />
          </PopoverTrigger>
          <PopoverContent align="start" className="w-80 p-3">
            <PopoverTitle className="text-heading">{copy.confidence.title}</PopoverTitle>
            <p className="text-small">{confidence.rationale}</p>
            <p className="text-meta text-muted-foreground">{copy.confidence.checks}</p>
            {notes.length ? (
              <ul className="flex list-disc flex-col gap-1 pl-4 text-small">
                {notes.map((note) => (
                  <li key={note}>{plainNote(note)}</li>
                ))}
              </ul>
            ) : (
              <p className="text-small">{copy.confidence.noNotes}</p>
            )}
          </PopoverContent>
        </Popover>
      </div>
      <p className="text-meta text-muted-foreground">{confidence.rationale}</p>
    </div>
  );
}
