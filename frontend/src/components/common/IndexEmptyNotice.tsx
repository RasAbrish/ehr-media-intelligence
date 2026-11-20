import { InfoIcon } from "lucide-react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { copy } from "@/lib/copy";

/** "Pipeline not run" state (docs/06 section 6.9). A status, not an error, so role=status. */
export function IndexEmptyNotice() {
  return (
    <Alert role="status" className="border-info/40">
      <InfoIcon aria-hidden="true" strokeWidth={1.75} className="text-info" />
      <AlertTitle className="text-heading">{copy.indexEmpty.title}</AlertTitle>
      <AlertDescription className="text-muted-foreground">
        {copy.indexEmpty.before}{" "}
        <code className="rounded-sm bg-muted px-1 py-0.5 font-mono text-mono text-foreground">
          {copy.indexEmpty.command}
        </code>
        {copy.indexEmpty.after}
      </AlertDescription>
    </Alert>
  );
}
