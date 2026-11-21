import type { ClinicalSummaryResponse } from "@/features/patients/schemas";
import { copy } from "@/lib/copy";
import { cn } from "@/lib/utils";

const STEPS = { low: 1, medium: 2, high: 3 } as const;

/** 3-step bar, level and score, with the rationale in words (docs/06 section 12.2). */
export function ConfidenceMeter({
  confidence,
}: {
  confidence: ClinicalSummaryResponse["confidence"];
}) {
  const level = copy.ai.confidenceLevels[confidence.level];
  const score = confidence.score.toFixed(2);
  return (
    <div className="flex flex-col gap-1">
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
      <p className="text-meta text-muted-foreground">{confidence.rationale}</p>
    </div>
  );
}
