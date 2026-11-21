import { SparklesIcon } from "lucide-react";

import { copy } from "@/lib/copy";
import { cn } from "@/lib/utils";

/** Violet AI marker (docs/06 sections 6.6 and 12). Every model-generated element carries it. */
export function AiBadge({
  className,
  label = copy.ai.badge,
}: {
  className?: string;
  label?: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex h-5 shrink-0 items-center gap-1 rounded-sm bg-ai-muted px-1.5 text-meta text-ai",
        className,
      )}
    >
      <SparklesIcon aria-hidden className="size-3" strokeWidth={1.75} />
      {label}
    </span>
  );
}
