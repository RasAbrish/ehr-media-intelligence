import { copy } from "@/lib/copy";
import { cn } from "@/lib/utils";

export type BadgeResourceType = keyof typeof copy.resourceLabels;

const TONES: Record<BadgeResourceType, string> = {
  DocumentReference: "bg-rt-document-bg text-rt-document border-rt-document/30",
  DiagnosticReport: "bg-rt-report-bg text-rt-report border-rt-report/30",
  Observation: "bg-rt-observation-bg text-rt-observation border-rt-observation/30",
  ClinicalSummary: "bg-ai-muted text-ai border-ai/30",
  Encounter: "bg-muted text-muted-foreground border-border",
};

export const TYPE_DOT: Record<BadgeResourceType, string> = {
  DocumentReference: "bg-rt-document",
  DiagnosticReport: "bg-rt-report",
  Observation: "bg-rt-observation",
  ClinicalSummary: "bg-ai",
  Encounter: "bg-muted-foreground",
};

/** Resource type badge: tinted background, 30 percent border, colored dot and a text label. */
export function ResourceTypeBadge({
  type,
  className,
}: {
  type: BadgeResourceType;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex h-5.5 shrink-0 items-center gap-1.5 rounded-sm border px-1.5 text-meta whitespace-nowrap",
        TONES[type],
        className,
      )}
    >
      <span aria-hidden className={cn("size-1.5 rounded-full", TYPE_DOT[type])} />
      {copy.resourceLabels[type]}
    </span>
  );
}
