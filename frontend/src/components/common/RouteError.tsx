import { CircleAlertIcon, RotateCwIcon } from "lucide-react";

import { Alert, AlertAction, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { copy } from "@/lib/copy";

const reloadPage = () => {
  window.location.reload();
};

/** A page or lazy chunk that failed to load, often after a deploy or with the server down. */
export function RouteError({ onReload = reloadPage }: { onReload?: () => void }) {
  return (
    <Alert variant="destructive" className="border-destructive/40">
      <CircleAlertIcon aria-hidden />
      <AlertTitle>{copy.errors.pageTitle}</AlertTitle>
      <AlertDescription>
        <p>{copy.errors.pageBody}</p>
      </AlertDescription>
      <AlertAction>
        <Button variant="outline" className="max-md:h-11" onClick={onReload}>
          <RotateCwIcon aria-hidden data-icon="inline-start" />
          {copy.errors.reload}
        </Button>
      </AlertAction>
    </Alert>
  );
}
