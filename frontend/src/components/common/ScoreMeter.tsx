import { copy } from "@/lib/copy";
import { formatScore, percent } from "@/lib/format";
import { cn } from "@/lib/utils";

const SEGMENTS = 5;

/** Relevance as a number plus a 5-segment bar (docs/06 section 6.5). */
export function ScoreMeter({
  score,
  compact = false,
  id,
}: {
  score: number;
  compact?: boolean;
  id?: string;
}) {
  const filled = Math.round(Math.min(Math.max(score, 0), 1) * SEGMENTS);
  return (
    <span
      id={id}
      role="img"
      aria-label={copy.card.relevance(percent(score))}
      className="inline-flex shrink-0 items-center gap-2"
    >
      <span className="font-mono text-mono text-foreground tabular-nums">{formatScore(score)}</span>
      <span aria-hidden className={cn("items-center gap-0.5", compact ? "hidden md:flex" : "flex")}>
        {Array.from({ length: SEGMENTS }, (_, index) => (
          <span
            key={index}
            className={cn("h-2.5 w-1 rounded-[1px]", index < filled ? "bg-primary" : "bg-muted")}
          />
        ))}
      </span>
    </span>
  );
}
