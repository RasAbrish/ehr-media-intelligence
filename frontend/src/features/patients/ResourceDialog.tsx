import { useQuery } from "@tanstack/react-query";
import { XIcon } from "lucide-react";

import { CopyButton } from "@/components/common/CopyButton";
import { ErrorState } from "@/components/common/ErrorState";
import { ResourceTypeBadge } from "@/components/common/ResourceTypeBadge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { resourceQuery } from "@/features/patients/api";
import type { ResourceDetail } from "@/features/patients/schemas";
import type { EvidenceRef } from "@/lib/common-schemas";
import { copy } from "@/lib/copy";
import { formatDate } from "@/lib/format";
import { cn } from "@/lib/utils";

interface ResourceDialogProps {
  target: EvidenceRef | null;
  onClose: () => void;
}

function Readable({ detail }: { detail: ResourceDetail }) {
  return (
    <div className="flex flex-col gap-4">
      {detail.sections.length ? (
        detail.sections.map((section, index) => (
          <section key={`${section.heading}-${index}`} className="flex flex-col gap-1">
            <h3 className="text-overline text-muted-foreground uppercase">{section.heading}</h3>
            <p className="max-w-[75ch] text-body whitespace-pre-line">{section.body}</p>
          </section>
        ))
      ) : detail.text ? (
        <p className="max-w-[75ch] text-body whitespace-pre-line">{detail.text}</p>
      ) : detail.observations.length ? null : (
        <p className="text-body text-muted-foreground italic">{copy.dialog.noText}</p>
      )}
      {detail.observations.length ? (
        <section className="flex flex-col gap-2">
          <h3 className="text-overline text-muted-foreground uppercase">{copy.dialog.results}</h3>
          <div className="rounded-lg border">
            <Table className="text-small">
              <TableHeader className="bg-muted">
                <TableRow>
                  <TableHead>{copy.dialog.resultColumns.name}</TableHead>
                  <TableHead className="text-right">{copy.dialog.resultColumns.value}</TableHead>
                  <TableHead>{copy.dialog.resultColumns.range}</TableHead>
                  <TableHead>{copy.dialog.resultColumns.flag}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {detail.observations.map((obs) => {
                  const abnormal = obs.interpretation && obs.interpretation !== "N";
                  const critical = obs.interpretation === "HH" || obs.interpretation === "LL";
                  return (
                    <TableRow key={obs.resource_id}>
                      <TableCell>{obs.name}</TableCell>
                      <TableCell className="text-right font-mono tabular-nums">
                        {obs.value} {obs.unit ?? ""}
                      </TableCell>
                      <TableCell className="text-muted-foreground">
                        {obs.reference_range ?? ""}
                      </TableCell>
                      <TableCell
                        className={cn(
                          critical
                            ? "font-medium text-destructive"
                            : abnormal
                              ? "font-medium"
                              : "text-muted-foreground",
                        )}
                      >
                        {obs.interpretation ?? ""}
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </div>
        </section>
      ) : null}
      {detail.issues.length ? (
        <section className="flex flex-col gap-1">
          <h3 className="text-overline text-muted-foreground uppercase">{copy.dialog.issues}</h3>
          <ul className="text-small">
            {detail.issues.map((issue) => (
              <li key={`${issue.code}-${issue.path}`}>
                <span className="font-medium">{issue.severity}</span> {issue.message}{" "}
                <span className="font-mono text-mono text-muted-foreground">{issue.path}</span>
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </div>
  );
}

/** One record: readable text and its FHIR JSON (docs/06 section 6.7). */
export function ResourceDialog({ target, onClose }: ResourceDialogProps) {
  const query = useQuery({
    ...resourceQuery(target?.resource_type ?? "", target?.resource_id ?? ""),
    enabled: target !== null,
  });
  const detail = query.data;
  const json = detail ? JSON.stringify(detail.fhir, null, 2) : "";
  return (
    <Dialog
      open={target !== null}
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
    >
      <DialogContent
        showCloseButton={false}
        className="flex max-h-[85dvh] w-full max-w-[calc(100%-2rem)] flex-col gap-4 sm:max-w-2xl"
      >
        <DialogHeader className="pr-10">
          <DialogTitle className="text-title">
            {detail?.resource.title ?? copy.drawer.loading}
          </DialogTitle>
          <DialogDescription
            render={<div />}
            className="flex flex-wrap items-center gap-2 text-meta"
          >
            {detail ? (
              <>
                <ResourceTypeBadge type={detail.resource.resource_type} />
                {detail.resource.date ? (
                  <time dateTime={detail.resource.date}>{formatDate(detail.resource.date)}</time>
                ) : null}
                <span>{detail.patient.display_name}</span>
              </>
            ) : null}
          </DialogDescription>
        </DialogHeader>
        {query.isError ? (
          <ErrorState
            title={copy.errors.recordTitle}
            error={query.error}
            onRetry={() => void query.refetch()}
          />
        ) : null}
        {query.isPending && target ? (
          <div className="flex flex-col gap-2">
            <Skeleton className="h-4 w-1/2" />
            <Skeleton className="h-20 w-full" />
          </div>
        ) : null}
        {detail ? (
          <Tabs defaultValue="readable" className="min-h-0 flex-1">
            <TabsList variant="line" className="group-data-horizontal/tabs:h-auto">
              <TabsTrigger value="readable" className="h-8 max-md:h-11">
                {copy.dialog.readable}
              </TabsTrigger>
              <TabsTrigger value="fhir" className="h-8 max-md:h-11">
                {copy.dialog.fhir}
              </TabsTrigger>
            </TabsList>
            <TabsContent value="readable" className="min-h-0 overflow-y-auto pt-2">
              <Readable detail={detail} />
            </TabsContent>
            <TabsContent value="fhir" className="relative min-h-0 overflow-y-auto pt-2">
              <CopyButton
                value={json}
                label={copy.dialog.copyJson}
                confirmation={copy.dialog.copied}
                className="absolute top-3 right-2"
              />
              <pre className="overflow-x-auto rounded-lg bg-muted p-3 font-mono text-mono">
                {json}
              </pre>
            </TabsContent>
          </Tabs>
        ) : null}
        <DialogClose
          render={
            <Button
              variant="ghost"
              size="icon"
              className="absolute top-2 right-2 max-md:size-11"
              aria-label={copy.dialog.close}
            />
          }
        >
          <XIcon aria-hidden />
        </DialogClose>
      </DialogContent>
    </Dialog>
  );
}
