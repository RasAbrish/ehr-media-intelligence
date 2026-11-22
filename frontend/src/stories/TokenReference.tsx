const COLORS = [
  "background",
  "foreground",
  "card",
  "card-foreground",
  "popover",
  "popover-foreground",
  "primary",
  "primary-foreground",
  "secondary",
  "secondary-foreground",
  "muted",
  "muted-foreground",
  "accent",
  "accent-foreground",
  "destructive",
  "border",
  "input",
  "ring",
  "warning",
  "warning-foreground",
  "success",
  "info",
  "ai",
  "ai-muted",
  "rt-document",
  "rt-document-bg",
  "rt-report",
  "rt-report-bg",
  "rt-observation",
  "rt-observation-bg",
  "overlay-shadow",
] as const;
const TYPE = [
  "text-display",
  "text-title",
  "text-heading",
  "text-body",
  "text-small",
  "text-meta",
  "text-mono",
  "text-overline",
] as const;
const SPACING = [1, 2, 3, 4, 5, 6, 8, 12] as const;

/** Rendered from the live CSS variables, so it cannot drift from src/index.css. */
export function TokenReference() {
  return (
    <div className="flex flex-col gap-6 text-small">
      <ul className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        {COLORS.map((name) => (
          <li key={name} className="flex items-center gap-2">
            <span className="size-8 rounded-md border" style={{ background: `var(--${name})` }} />
            <code>{name}</code>
          </li>
        ))}
      </ul>
      <ul>
        {TYPE.map((name) => (
          <li key={name} className={name}>
            {name}
          </li>
        ))}
      </ul>
      <ul>
        {SPACING.map((step) => (
          <li key={step} className="flex items-center gap-2">
            <span className="h-3 bg-primary" style={{ width: `calc(var(--spacing) * ${step})` }} />
            <code>{step}</code>
          </li>
        ))}
      </ul>
    </div>
  );
}
