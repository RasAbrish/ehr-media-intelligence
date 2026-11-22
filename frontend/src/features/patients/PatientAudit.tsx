import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { EmptyState } from "@/components/common/EmptyState";
import { ErrorState } from "@/components/common/ErrorState";
import { Pagination } from "@/components/common/Pagination";
import { Skeleton } from "@/components/ui/skeleton";
import { patientAuditQuery } from "@/features/patients/api";
import { IssueSeverity, SeverityFilter } from "@/features/quality/SeverityControls";
import type { Severity } from "@/lib/contract-enums";
import { copy } from "@/lib/copy";

const PAGE_SIZE = 25;

/** The drawer's Data quality tab: what cleaning changed for this patient, PHI masked. */
export function PatientAudit({ patientKey }: { patientKey: string }) {
  const [severity, setSeverity] = useState<Severity>();
  const [page, setPage] = useState(1);
  const query = useQuery(patientAuditQuery(patientKey, { page, size: PAGE_SIZE, severity }));
  return (
    <div className="flex flex-col gap-3">
      <SeverityFilter
        value={severity}
        onChange={(next) => {
          setSeverity(next);
          setPage(1);
        }}
      />
      {query.isError ? (
        <ErrorState
          title={copy.errors.qualityTitle}
          error={query.error}
          onRetry={() => void query.refetch()}
        />
      ) : !query.data ? (
        <Skeleton className="h-40 w-full" />
      ) : query.data.total === 0 ? (
        <EmptyState
          headingLevel="h3"
          title={copy.quality.noMatchTitle}
          description={copy.quality.noMatchBody}
        />
      ) : (
        <>
          <ul className="flex flex-col divide-y rounded-lg border">
            {query.data.items.map((entry) => (
              <li key={entry.id} className="flex flex-col gap-1 p-2.5 text-small">
                <p className="flex flex-wrap items-center gap-2">
                  <IssueSeverity severity={entry.severity} />
                  <span className="font-mono text-mono break-all">{entry.rule}</span>
                  {entry.field ? (
                    <span className="text-meta text-muted-foreground">{entry.field}</span>
                  ) : null}
                </p>
                <p>{entry.message}</p>
                {entry.before !== null || entry.after !== null ? (
                  <dl className="grid grid-cols-[auto_1fr] gap-x-2 text-meta text-muted-foreground">
                    <dt>{copy.quality.columns.before}</dt>
                    <dd className="font-mono break-all">{entry.before}</dd>
                    <dt>{copy.quality.columns.after}</dt>
                    <dd className="font-mono break-all">{entry.after}</dd>
                  </dl>
                ) : null}
              </li>
            ))}
          </ul>
          <Pagination
            page={query.data.page}
            pageSize={query.data.page_size}
            total={query.data.total}
            totalPages={query.data.total_pages}
            onPage={setPage}
          />
        </>
      )}
    </div>
  );
}
