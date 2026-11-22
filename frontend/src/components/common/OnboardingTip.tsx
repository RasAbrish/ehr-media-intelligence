import { InfoIcon, XIcon } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { copy } from "@/lib/copy";
import { focusPageSearch } from "@/lib/keyboard";
import { readStored, writeStored } from "@/lib/storage";

const FLAG = "ehr-mip.tip-dismissed";

/** First-run tip under the search input (docs/06 section 12.4). No modal tours. */
export function OnboardingTip() {
  const [dismissed, setDismissed] = useState(() => readStored(FLAG) !== null);
  if (dismissed) return null;
  return (
    <div className="flex items-center gap-2 rounded-md bg-muted py-1 pr-1 pl-3 text-small">
      <InfoIcon aria-hidden className="size-4 shrink-0 text-info" />
      <p className="flex-1">{copy.tip.body}</p>
      <Button
        variant="ghost"
        size="icon"
        className="shrink-0 max-md:size-11"
        aria-label={copy.tip.dismiss}
        onClick={() => {
          writeStored(FLAG, "1");
          setDismissed(true);
          focusPageSearch(); // the button is about to unmount
        }}
      >
        <XIcon aria-hidden />
      </Button>
    </div>
  );
}
