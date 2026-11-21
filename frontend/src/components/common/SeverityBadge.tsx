import type { AnomalySeverity } from "@/lib/contract-enums";
import { copy } from "@/lib/copy";
import { cn } from "@/lib/utils";

const TONES: Record<AnomalySeverity, string> = {
  high: "border-destructive/30 bg-destructive/10 text-destructive",
  moderate: "border-warning/40 bg-warning/15 text-warning-foreground dark:text-warning",
  low: "border-border bg-muted text-muted-foreground",
};

/** Severity has a text label, never color alone (docs/06 sections 3.3 and 9). */
export function SeverityBadge({
  severity,
  suffix,
}: {
  severity: AnomalySeverity;
  suffix?: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex h-5.5 shrink-0 items-center gap-1.5 rounded-sm border px-1.5 text-meta",
        TONES[severity],
      )}
    >
      {severity === "high" && <span aria-hidden className="size-1.5 rounded-full bg-destructive" />}
      {copy.ai.severity[severity]}
      {suffix ? ` · ${suffix}` : null}
    </span>
  );
}
