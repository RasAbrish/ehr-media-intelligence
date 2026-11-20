import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

interface PageHeaderProps {
  title: string;
  description?: ReactNode;
  size?: "display" | "title";
  className?: string;
}

export function PageHeader({ title, description, size = "title", className }: PageHeaderProps) {
  return (
    <div className={cn("flex flex-col gap-1", className)}>
      <h1 className={size === "display" ? "text-display" : "text-title"}>{title}</h1>
      {description !== undefined && (
        <p className="max-w-[75ch] text-muted-foreground">{description}</p>
      )}
    </div>
  );
}
