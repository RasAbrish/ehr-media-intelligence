import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

interface EmptyStateProps {
  title: string;
  description: string;
  action?: ReactNode;
  className?: string;
  headingLevel?: "h2" | "h3";
}

export function EmptyState({
  title,
  description,
  action,
  className,
  headingLevel = "h2",
}: EmptyStateProps) {
  const Heading = headingLevel;
  return (
    <div
      className={cn(
        "flex flex-col items-start gap-2 rounded-xl border border-dashed px-5 py-8",
        className,
      )}
    >
      <Heading className="text-heading">{title}</Heading>
      <p className="max-w-prose text-body text-muted-foreground">{description}</p>
      {action ? <div className="mt-2">{action}</div> : null}
    </div>
  );
}
