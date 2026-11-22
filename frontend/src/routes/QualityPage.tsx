import { useQuery } from "@tanstack/react-query";
import { useNavigate, useSearch } from "@tanstack/react-router";

import { ErrorState } from "@/components/common/ErrorState";
import { IndexEmptyNotice } from "@/components/common/IndexEmptyNotice";
import { PageHeader } from "@/components/common/PageHeader";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { overviewQuery } from "@/features/quality/api";
import { KpiStrip } from "@/features/quality/KpiStrip";
import {
  QUALITY_TABS,
  type QualityPageParams,
  type QualityTab,
} from "@/features/quality/quality-params";
import { AuditPanel, IssuesPanel, QuarantinePanel } from "@/features/quality/QualityTables";
import { SeverityFilter } from "@/features/quality/SeverityControls";
import { copy } from "@/lib/copy";

const DEFAULT_SIZE = 50;

/** Data quality dashboard (docs/06 section 6.10, FR-5.8). */
export function QualityPage() {
  const search = useSearch({ from: "/quality" });
  const navigate = useNavigate({ from: "/quality" });
  const overview = useQuery(overviewQuery());
  const tab = search.tab ?? "issues";

  const change = (next: QualityPageParams) => {
    void navigate({ search: (prev) => ({ ...prev, page: undefined, ...next }), replace: true });
  };
  const paging = {
    onPage: (page: number) => {
      change({ page });
    },
    onPageSize: (size: number) => {
      change({ size });
    },
  };
  const params = {
    page: search.page ?? 1,
    size: search.size ?? DEFAULT_SIZE,
    severity: tab === "quarantine" ? undefined : search.severity,
  };

  return (
    <section className="flex flex-col gap-4">
      <PageHeader title={copy.quality.title} description={copy.quality.body} />
      {overview.isError ? (
        <ErrorState
          title={copy.errors.qualityTitle}
          error={overview.error}
          onRetry={() => void overview.refetch()}
        />
      ) : !overview.data ? (
        <Skeleton className="h-20 w-full" />
      ) : overview.data.validation.bundles === 0 ? (
        <IndexEmptyNotice />
      ) : (
        <>
          <KpiStrip overview={overview.data} />
          <Tabs
            value={tab}
            onValueChange={(value) => {
              change({ tab: value as QualityTab, severity: undefined });
            }}
            className="gap-3"
          >
            <div className="flex flex-wrap items-center justify-between gap-2 border-b pb-1">
              <TabsList
                variant="line"
                className="flex-wrap justify-start gap-3 group-data-horizontal/tabs:h-auto"
              >
                {QUALITY_TABS.map((value) => (
                  <TabsTrigger key={value} value={value} className="h-8 flex-none max-md:h-11">
                    {copy.quality.tabs[value]}
                  </TabsTrigger>
                ))}
              </TabsList>
              {tab === "quarantine" ? null : (
                <SeverityFilter
                  value={search.severity}
                  onChange={(severity) => {
                    change({ severity });
                  }}
                />
              )}
            </div>
            <TabsContent value="issues">
              <IssuesPanel params={params} {...paging} />
            </TabsContent>
            <TabsContent value="audit">
              <AuditPanel params={params} {...paging} />
            </TabsContent>
            <TabsContent value="quarantine">
              <QuarantinePanel params={params} {...paging} />
            </TabsContent>
          </Tabs>
        </>
      )}
    </section>
  );
}
