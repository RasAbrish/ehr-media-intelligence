import { ArrowUpRightIcon } from "lucide-react";

import type { PatientResourceItem } from "@/features/patients/schemas";
import type { EvidenceRef } from "@/lib/common-schemas";
import { copy } from "@/lib/copy";
import { formatDate } from "@/lib/format";

interface EvidenceChipProps {
  evidence: EvidenceRef;
  resources: Map<string, PatientResourceItem>;
  onOpen: (evidence: EvidenceRef) => void;
  /** Arrow only, for table rows where the record is already named (docs/06 section 12.1). */
  iconOnly?: boolean;
}

/** "{record} · {date}" link to the cited source record (docs/06 section 12.2). */
export function EvidenceChip({ evidence, resources, onOpen, iconOnly = false }: EvidenceChipProps) {
  const record = resources.get(evidence.resource_id);
  const label = record?.title ?? copy.resourceLabels[evidence.resource_type];
  const short = formatDate(record?.date);
  const text = short ? `${label} · ${short}` : label;
  // The accessible name contains the visible text (WCAG 2.5.3, label in name).
  const name = copy.ai.evidence(text);
  if (iconOnly) {
    return (
      <button
        type="button"
        onClick={() => {
          onOpen(evidence);
        }}
        aria-label={name}
        title={text}
        className="inline-flex size-8 items-center justify-center rounded-md text-muted-foreground hover:bg-muted hover:text-foreground focus-visible:outline-2 focus-visible:outline-ring max-md:size-11"
      >
        <ArrowUpRightIcon aria-hidden className="size-4" />
      </button>
    );
  }
  return (
    <button
      type="button"
      onClick={() => {
        onOpen(evidence);
      }}
      aria-label={name}
      title={text}
      className="inline-flex min-h-8 max-w-full items-center gap-1 rounded-md border bg-card px-2 font-mono text-meta text-muted-foreground hover:border-ring hover:text-foreground focus-visible:outline-2 focus-visible:outline-ring max-md:min-h-11"
    >
      <ArrowUpRightIcon aria-hidden className="size-3.5 shrink-0" />
      <span className="min-w-0 py-1 text-left wrap-anywhere">{text}</span>
    </button>
  );
}
