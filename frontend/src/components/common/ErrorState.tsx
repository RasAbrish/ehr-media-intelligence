import { CircleAlertIcon, RotateCwIcon } from "lucide-react";

import { Alert, AlertAction, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { copy } from "@/lib/copy";
import { ApiError, ContractError, NetworkError } from "@/lib/problem";

/** Message for an error following the formula "what happened, why, what to do" (docs/06 14.3). */
export function errorMessage(error: unknown): string {
  if (error instanceof NetworkError) return copy.errors.network;
  if (error instanceof ContractError) return copy.errors.contract;
  if (error instanceof ApiError) {
    // Shown after the automatic retry failed, so the user is told to act.
    if (error.status === 429) return copy.errors.rateLimitedFinal(error.retryAfterSeconds ?? 60);
    if (error.code === "not_ready") return copy.errors.notReady;
    if (error.status === 422) {
      const loc = error.problem?.errors[0]?.loc ?? "";
      return loc.includes("date_") ? copy.errors.rangeInvalid : copy.errors.validation;
    }
    if (error.status >= 500) {
      return error.requestId
        ? copy.errors.server(error.requestId.slice(0, 8))
        : copy.errors.serverNoId;
    }
    return copy.errors.request;
  }
  return copy.errors.serverNoId;
}

interface ErrorStateProps {
  error: unknown;
  onRetry?: () => void;
  title?: string;
}

/** Destructive outline alert with retry and the request id in mono (docs/06 section 6.9). */
export function ErrorState({ error, onRetry, title = copy.errors.title }: ErrorStateProps) {
  const requestId = error instanceof ApiError ? error.requestId : null;
  return (
    <Alert
      variant="destructive"
      className="border-destructive/40 has-data-[slot=alert-action]:pr-28"
    >
      <CircleAlertIcon aria-hidden />
      <AlertTitle>{title}</AlertTitle>
      <AlertDescription>
        <p>{errorMessage(error)}</p>
        {requestId ? (
          <p className="text-meta text-muted-foreground">
            {copy.errors.requestId}{" "}
            <span className="font-mono text-mono select-all">{requestId}</span>
          </p>
        ) : null}
      </AlertDescription>
      {onRetry ? (
        <AlertAction>
          <Button variant="outline" className="max-md:h-11" onClick={onRetry}>
            <RotateCwIcon aria-hidden data-icon="inline-start" />
            {copy.errors.retry}
          </Button>
        </AlertAction>
      ) : null}
    </Alert>
  );
}
