import { useId } from "react";

import { SeveritySchema, type Severity } from "@/lib/contract-enums";
import { copy } from "@/lib/copy";
import { cn } from "@/lib/utils";

const TONES: Record<Severity, string> = {
  error: "border-destructive/30 bg-destructive/10 text-destructive",
  warning: "border-warning/40 bg-warning/15 text-warning-foreground dark:text-warning",
  info: "border-border bg-muted text-muted-foreground",
};

/** Data quality severity, always with its text label. */
export function IssueSeverity({ severity }: { severity: Severity }) {
  return (
    <span
      className={cn(
        "inline-flex h-5.5 items-center rounded-sm border px-1.5 text-meta",
        TONES[severity],
      )}
    >
      {copy.quality.severities[severity]}
    </span>
  );
}

interface SeverityFilterProps {
  value: Severity | undefined;
  onChange: (next: Severity | undefined) => void;
}

export function SeverityFilter({ value, onChange }: SeverityFilterProps) {
  const id = useId();
  return (
    <div className="flex items-center gap-2">
      <label htmlFor={id} className="text-meta text-muted-foreground">
        {copy.quality.severity}
      </label>
      <select
        id={id}
        value={value ?? ""}
        onChange={(event) => {
          onChange(SeveritySchema.options.find((option) => option === event.target.value));
        }}
        className="h-8 rounded-lg border border-input bg-card px-2 text-small max-md:h-11"
      >
        <option value="">{copy.quality.allSeverities}</option>
        {SeveritySchema.options.map((option) => (
          <option key={option} value={option}>
            {copy.quality.severities[option]}
          </option>
        ))}
      </select>
    </div>
  );
}
