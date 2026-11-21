import { DatabaseIcon, InfoIcon, TriangleAlertIcon } from "lucide-react";
import type { ReactNode } from "react";

import { AiBadge } from "@/components/common/AiBadge";
import { SeverityBadge } from "@/components/common/SeverityBadge";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { ConfidenceMeter } from "@/features/patients/ConfidenceMeter";
import { EvidenceChip } from "@/features/patients/EvidenceChip";
import type { ClinicalSummaryResponse, PatientResourceItem } from "@/features/patients/schemas";
import type { EvidenceRef } from "@/lib/common-schemas";
import { copy } from "@/lib/copy";
import { formatDate, formatDateTime } from "@/lib/format";

interface SummaryPanelProps {
  summary: ClinicalSummaryResponse;
  resources: Map<string, PatientResourceItem>;
  onEvidence: (evidence: EvidenceRef) => void;
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="flex flex-col gap-2">
      <h3 className="text-overline text-muted-foreground uppercase">{title}</h3>
      {children}
    </section>
  );
}

function NotDocumented() {
  return <p className="text-body text-muted-foreground italic">{copy.ai.notDocumented}</p>;
}

/** AI summary panel (docs/06 section 12.1). Generated content sits behind a violet rule. */
export function SummaryPanel({ summary, resources, onEvidence }: SummaryPanelProps) {
  const extractive = summary.provider === "extractive";
  const fellBack = summary.guardrail_notes.some((note) => note.startsWith("fallback_extractive"));
  const chief = summary.chief_concern.trim();
  return (
    <div className="flex flex-col gap-6 border-l-2 border-ai pl-4">
      <div
        role="note"
        className="flex gap-2.5 rounded-md border-l-3 border-ai bg-ai-muted px-3 py-2.5 text-small"
      >
        <InfoIcon aria-hidden className="mt-0.5 size-4 shrink-0 text-ai" />
        <p>{summary.disclaimer}</p>
      </div>

      <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-meta text-muted-foreground">
        <AiBadge label={copy.ai.summaryLabel} />
        <span>{copy.ai.generated(formatDateTime(summary.generated_at))}</span>
        {extractive ? (
          <Tooltip>
            <TooltipTrigger className="rounded-sm border border-info/40 px-1.5 text-info focus-visible:outline-2 focus-visible:outline-ring">
              {copy.ai.offline}
            </TooltipTrigger>
            <TooltipContent>{copy.ai.offlineHint}</TooltipContent>
          </Tooltip>
        ) : (
          <span className="font-mono text-mono">{summary.model}</span>
        )}
        <span>{copy.ai.promptVersion(summary.prompt_version)}</span>
        {summary.cached ? (
          <span className="inline-flex items-center gap-1 rounded-sm border px-1.5">
            <DatabaseIcon aria-hidden className="size-3" />
            {copy.ai.cached}
          </span>
        ) : null}
      </div>

      {fellBack ? (
        <p
          role="status"
          className="flex gap-2 rounded-md border border-info/40 px-3 py-2 text-small"
        >
          <InfoIcon aria-hidden className="mt-0.5 size-4 shrink-0 text-info" />
          {copy.ai.fallbackNotice}
        </p>
      ) : null}

      <Section title={copy.ai.sections.chief}>
        {chief && chief !== copy.ai.notDocumented ? (
          <p className="max-w-[75ch] text-body">{chief}</p>
        ) : (
          <NotDocumented />
        )}
      </Section>

      <Section title={copy.ai.sections.diagnoses}>
        {summary.key_diagnoses.length ? (
          <ul className="flex flex-col gap-2">
            {summary.key_diagnoses.map((diagnosis) => (
              <li key={diagnosis.name} className="flex flex-wrap items-center gap-2">
                <span className="text-body font-medium">{diagnosis.name}</span>
                {diagnosis.status === "suspected" ? (
                  <Tooltip>
                    <TooltipTrigger className="inline-flex h-5.5 items-center gap-1 rounded-sm border border-warning/40 bg-warning/15 px-1.5 text-meta text-warning-foreground focus-visible:outline-2 focus-visible:outline-ring dark:text-warning">
                      <TriangleAlertIcon aria-hidden className="size-3.5" />
                      {copy.ai.suspected}
                    </TooltipTrigger>
                    <TooltipContent>{copy.ai.suspectedHint}</TooltipContent>
                  </Tooltip>
                ) : (
                  <span className="inline-flex h-5.5 items-center rounded-sm border px-1.5 text-meta text-muted-foreground">
                    {copy.ai.status[diagnosis.status]}
                  </span>
                )}
                {diagnosis.evidence.map((evidence) => (
                  <EvidenceChip
                    key={evidence.resource_id}
                    evidence={evidence}
                    resources={resources}
                    onOpen={onEvidence}
                  />
                ))}
              </li>
            ))}
          </ul>
        ) : (
          <NotDocumented />
        )}
      </Section>

      <Section title={copy.ai.sections.media}>
        {summary.recent_media.length ? (
          <ul className="flex flex-col divide-y rounded-md border">
            {summary.recent_media.map((media) => (
              <li
                key={media.resource.resource_id}
                className="grid grid-cols-[4rem_6rem_minmax(0,1fr)_2rem] items-start gap-x-2 px-2.5 py-1.5 text-small max-sm:grid-cols-[minmax(0,1fr)_2rem] max-sm:gap-y-0.5"
              >
                {/* One line for kind and date on phones; two grid columns from sm up. */}
                <span className="flex gap-2 pt-0.5 text-meta text-muted-foreground sm:contents">
                  <span className="sm:pt-0.5">{copy.ai.kinds[media.kind]}</span>
                  <time dateTime={media.date ?? undefined} className="tabular-nums sm:pt-0.5">
                    {formatDate(media.date) ?? copy.ai.undated}
                  </time>
                </span>
                <span className="max-sm:col-span-2 max-sm:row-start-2">{media.finding}</span>
                <span className="-mt-1 max-sm:col-start-2 max-sm:row-start-1">
                  <EvidenceChip
                    evidence={media.resource}
                    resources={resources}
                    onOpen={onEvidence}
                    iconOnly
                  />
                </span>
              </li>
            ))}
          </ul>
        ) : (
          <NotDocumented />
        )}
      </Section>

      <Section title={copy.ai.sections.anomalies}>
        {summary.flagged_anomalies.length ? (
          <ul className="flex flex-col gap-2">
            {summary.flagged_anomalies.map((anomaly) => {
              const dataQuality = anomaly.severity === "low" && anomaly.source === "rule";
              return (
                <li key={anomaly.description} className="flex flex-wrap items-center gap-2">
                  {dataQuality ? (
                    <Tooltip>
                      <TooltipTrigger className="inline-flex focus-visible:outline-2 focus-visible:outline-ring">
                        <SeverityBadge severity={anomaly.severity} suffix={copy.ai.dq} />
                      </TooltipTrigger>
                      <TooltipContent>{copy.ai.dqHint}</TooltipContent>
                    </Tooltip>
                  ) : (
                    <SeverityBadge severity={anomaly.severity} />
                  )}
                  <span className="text-body">{anomaly.description}</span>
                  {anomaly.evidence.map((evidence) => (
                    <EvidenceChip
                      key={evidence.resource_id}
                      evidence={evidence}
                      resources={resources}
                      onOpen={onEvidence}
                    />
                  ))}
                </li>
              );
            })}
          </ul>
        ) : (
          <NotDocumented />
        )}
      </Section>

      <Section title={copy.ai.sections.overview}>
        {summary.overview.trim() && summary.overview !== copy.ai.notDocumented ? (
          <p className="max-w-[75ch] text-body">{summary.overview}</p>
        ) : (
          <NotDocumented />
        )}
      </Section>

      <div className="border-t pt-4">
        <ConfidenceMeter confidence={summary.confidence} />
      </div>
    </div>
  );
}
