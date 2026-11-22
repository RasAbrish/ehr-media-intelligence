import { useQuery } from "@tanstack/react-query";
import { ArrowLeftIcon, TriangleAlertIcon, XIcon } from "lucide-react";
import { lazy, Suspense, useEffect, useMemo, useRef, useState } from "react";

import { CopyButton } from "@/components/common/CopyButton";
import { EmptyState } from "@/components/common/EmptyState";
import { ErrorState } from "@/components/common/ErrorState";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { SheetClose, SheetDescription, SheetTitle } from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { patientQuery, resourcesQuery, summaryQuery } from "@/features/patients/api";
import { DrawerSkeleton } from "@/features/patients/DrawerSkeleton";
import { PatientAudit } from "@/features/patients/PatientAudit";
import type { PatientDetail, PatientResourceItem } from "@/features/patients/schemas";
import { SummaryPanel } from "@/features/patients/SummaryPanel";
import type { EvidenceRef } from "@/lib/common-schemas";
import { copy } from "@/lib/copy";
import { ageSex, formatDate } from "@/lib/format";
import { isTypingTarget } from "@/lib/keyboard";
import { modalOpen } from "@/lib/modal";
import { ApiError } from "@/lib/problem";

const ResourceDialog = lazy(() =>
  import("@/features/patients/ResourceDialog").then((m) => ({ default: m.ResourceDialog })),
);
const loadTable = () => import("@/features/patients/ResourceTable");
const ResourceTable = lazy(() => loadTable().then((m) => ({ default: m.ResourceTable })));
const TABS = ["summary", "records", "quality"] as const;
const HIGHLIGHT_MS = 1200;
type Tab = (typeof TABS)[number];

function Header({ patient }: { patient: PatientDetail }) {
  const who = ageSex(patient.age, patient.gender);
  const born = formatDate(patient.birth_date);
  const old = patient.identifiers.filter((i) => i.use === "old").map((i) => i.value);
  return (
    <div className="flex flex-col gap-1.5">
      <SheetTitle className="pr-10 text-title">{patient.display_name}</SheetTitle>
      <SheetDescription
        render={<div />}
        className="flex flex-wrap items-center gap-x-2 gap-y-0.5 text-small text-muted-foreground"
      >
        <span className="inline-flex items-center gap-0.5 font-mono text-mono">
          {copy.card.mrn(patient.mrn)}
          <CopyButton
            value={patient.mrn}
            label={copy.card.copyMrn}
            confirmation={copy.card.copied(patient.mrn)}
          />
        </span>
        <span aria-hidden>·</span>
        <span title={who.long}>{who.short}</span>
        {born ? (
          <>
            <span aria-hidden>·</span>
            <span>{copy.drawer.born(born)}</span>
          </>
        ) : null}
      </SheetDescription>
      {old.length ? (
        <p className="flex flex-wrap items-center gap-x-2 gap-y-0.5 text-small">
          <span className="inline-flex items-center gap-1 rounded-sm border border-warning/40 bg-warning/10 px-1.5 text-meta text-warning-foreground dark:text-warning">
            <TriangleAlertIcon aria-hidden className="size-3.5" />
            {copy.drawer.mergedTitle(old.length + 1)}
          </span>
          <span className="font-mono text-mono text-muted-foreground">
            {copy.drawer.alsoKnown(old.join(", MRN "))}
          </span>
        </p>
      ) : null}
      {patient.identity_conflict ? (
        <Alert className="mt-1 border-warning/50 bg-warning/10">
          <TriangleAlertIcon aria-hidden className="text-warning-foreground dark:text-warning" />
          <AlertTitle>{copy.drawer.conflictTitle}</AlertTitle>
          <AlertDescription>{copy.drawer.conflictBody}</AlertDescription>
        </Alert>
      ) : null}
    </div>
  );
}

/** Everything inside the drawer; a lazy chunk (see PatientDrawer). */
export function DrawerBody({ patientKey }: { patientKey: string }) {
  const [tab, setTab] = useState<Tab>("summary");
  const [highlight, setHighlight] = useState<string | null>(null);
  // Bumped per evidence click so the table remounts with clear filters; never reset,
  // so the highlight fading out does not remount it again.
  const [tableKey, setTableKey] = useState(0);
  const [dialog, setDialog] = useState<EvidenceRef | null>(null);
  const [dialogUsed, setDialogUsed] = useState(false);
  const highlightTimer = useRef<number | undefined>(undefined);

  const patient = useQuery(patientQuery(patientKey));
  const summary = useQuery(summaryQuery(patientKey));
  const resources = useQuery(resourcesQuery(patientKey));

  // TanStack Table is too big for the first load; fetch it as soon as a drawer opens.
  useEffect(() => {
    loadTable().catch(() => undefined); // rendering the tab reports a failed load
  }, []);

  useEffect(
    () => () => {
      window.clearTimeout(highlightTimer.current);
    },
    [],
  );

  const byId = useMemo(
    () =>
      new Map<string, PatientResourceItem>(
        (resources.data?.items ?? []).map((item) => [item.resource_id, item]),
      ),
    [resources.data],
  );

  const onEvidence = (evidence: EvidenceRef) => {
    setTab("records");
    setHighlight(evidence.resource_id);
    setTableKey((key) => key + 1);
    window.clearTimeout(highlightTimer.current);
    highlightTimer.current = window.setTimeout(() => {
      setHighlight(null);
    }, HIGHLIGHT_MS);
  };

  // "[" and "]" switch tabs while the drawer is open (docs/06 section 8.4).
  useEffect(() => {
    const onKey = (event: globalThis.KeyboardEvent) => {
      if (isTypingTarget(event.target)) return;
      if (event.key !== "[" && event.key !== "]") return;
      if (modalOpen("dialog")) return; // a record dialog sits on top of the tabs
      event.preventDefault();
      setTab((current) => {
        const index = TABS.indexOf(current) + (event.key === "]" ? 1 : -1);
        return TABS[(index + TABS.length) % TABS.length] ?? "summary";
      });
    };
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("keydown", onKey);
    };
  }, []);

  const notFound = patient.error instanceof ApiError && patient.error.code === "patient_not_found";
  const summaryMissing =
    summary.error instanceof ApiError && summary.error.code === "summary_not_found";

  return (
    <div className="flex min-h-full shrink-0 flex-col">
      <div className="sticky top-0 z-20 flex flex-col gap-3 border-b bg-popover px-5 pt-4 pb-3">
        <div className="flex items-start gap-2">
          <SheetClose
            render={
              <Button
                variant="ghost"
                size="icon"
                className="-ml-2 size-11 md:hidden"
                aria-label={copy.drawer.back}
              />
            }
          >
            <ArrowLeftIcon aria-hidden />
          </SheetClose>
          <div className="min-w-0 flex-1">
            {patient.data ? (
              <Header patient={patient.data} />
            ) : (
              <SheetTitle className="text-title">
                {notFound ? copy.drawer.notFoundTitle : copy.drawer.loading}
              </SheetTitle>
            )}
          </div>
          <SheetClose
            render={
              <Button
                variant="ghost"
                size="icon"
                className="max-md:hidden"
                aria-label={copy.drawer.close}
              />
            }
          >
            <XIcon aria-hidden />
          </SheetClose>
        </div>
      </div>

      {notFound ? (
        <div className="p-5">
          <EmptyState
            headingLevel="h3"
            title={copy.drawer.notFoundTitle}
            description={copy.drawer.notFoundBody}
          />
        </div>
      ) : patient.isError ? (
        <div className="p-5">
          <ErrorState
            title={copy.errors.patientTitle}
            error={patient.error}
            onRetry={() => void patient.refetch()}
          />
        </div>
      ) : !patient.data ? (
        <DrawerSkeleton />
      ) : (
        <Tabs
          value={tab}
          onValueChange={(value) => {
            setTab(value as Tab);
          }}
          className="gap-0"
        >
          <TabsList
            variant="line"
            className="w-full justify-start gap-4 border-b px-5 group-data-horizontal/tabs:h-auto"
          >
            <TabsTrigger value="summary" className="h-8 flex-none max-md:h-11">
              {copy.drawer.tabs.summary}
            </TabsTrigger>
            <TabsTrigger value="records" className="h-8 flex-none max-md:h-11">
              {copy.drawer.tabs.records(resources.data ? resources.data.total : null)}
            </TabsTrigger>
            <TabsTrigger value="quality" className="h-8 flex-none max-md:h-11">
              {copy.drawer.tabs.quality}
            </TabsTrigger>
          </TabsList>
          <TabsContent value="summary" className="p-5">
            {summary.data ? (
              <SummaryPanel summary={summary.data} resources={byId} onEvidence={onEvidence} />
            ) : summaryMissing ? (
              <EmptyState
                headingLevel="h3"
                title={copy.ai.missingTitle}
                description={copy.ai.missingBody}
              />
            ) : summary.isError ? (
              <ErrorState
                title={copy.errors.summaryTitle}
                error={summary.error}
                onRetry={() => void summary.refetch()}
              />
            ) : (
              <div role="status" aria-busy="true" className="flex flex-col gap-3">
                <p className="text-small text-muted-foreground">{copy.ai.generating}</p>
                <Skeleton className="h-12 w-full" />
                <Skeleton className="h-4 w-2/3" />
                <Skeleton className="h-4 w-1/2" />
              </div>
            )}
          </TabsContent>
          <TabsContent value="records" className="p-5">
            {resources.data ? (
              <Suspense fallback={<Skeleton className="h-40 w-full" />}>
                <ResourceTable
                  key={tableKey}
                  items={resources.data.items}
                  highlightedId={highlight}
                  onOpen={(item) => {
                    setDialogUsed(true);
                    setDialog({
                      resource_type: item.resource_type as EvidenceRef["resource_type"],
                      resource_id: item.resource_id,
                    });
                  }}
                />
              </Suspense>
            ) : resources.isError ? (
              <ErrorState
                title={copy.errors.recordsTitle}
                error={resources.error}
                onRetry={() => void resources.refetch()}
              />
            ) : (
              <Skeleton className="h-40 w-full" />
            )}
          </TabsContent>
          <TabsContent value="quality" className="p-5">
            <PatientAudit patientKey={patientKey} />
          </TabsContent>
        </Tabs>
      )}
      {/* Loaded on first use, then kept so closing animates and returns focus. */}
      {dialogUsed ? (
        <Suspense fallback={null}>
          <ResourceDialog
            target={dialog}
            onClose={() => {
              setDialog(null);
            }}
          />
        </Suspense>
      ) : null}
    </div>
  );
}
