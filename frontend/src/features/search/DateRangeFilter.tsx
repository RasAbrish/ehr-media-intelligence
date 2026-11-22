import { parseISO } from "date-fns";
import { CalendarIcon, ChevronDownIcon } from "lucide-react";
import { lazy, Suspense, useMemo, useRef, useState } from "react";
import type { DateRange } from "react-day-picker";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { datePresets, iso } from "@/features/search/filters";
import { DateRangeSchema } from "@/features/search/search-params";
import { copy } from "@/lib/copy";
import { formatDate } from "@/lib/format";

const RangeCalendar = lazy(() =>
  import("@/components/common/RangeCalendar").then((m) => ({ default: m.RangeCalendar })),
);

interface Props {
  from: string | null;
  to: string | null;
  onChange: (next: { from: string | null; to: string | null }) => void;
  today?: Date;
  months?: number;
}

export function rangeLabel(from: string | null, to: string | null, today = new Date()): string {
  if (!from && !to) return copy.filters.dateAny;
  const preset = datePresets(today).find((p) => p.from === from && p.to === to);
  if (preset) return preset.label;
  if (from && to) return `${formatDate(from)} to ${formatDate(to)}`;
  return from ? `${copy.filters.from} ${formatDate(from)}` : `${copy.filters.to} ${formatDate(to)}`;
}

/** Presets plus a range calendar. The calendar cannot produce an end before the start. */
export function DateRangePicker({ from, to, onChange, today = new Date(), months = 2 }: Props) {
  const [error, setError] = useState<string | null>(null);
  const selected: DateRange | undefined = useMemo(
    () => (from ? { from: parseISO(from), to: to ? parseISO(to) : undefined } : undefined),
    [from, to],
  );
  const apply = (next: { from: string | null; to: string | null }) => {
    const checked = DateRangeSchema.safeParse(next);
    if (!checked.success) {
      setError(copy.filters.rangeError);
      return;
    }
    setError(null);
    onChange(next);
  };
  const calendarRef = useRef<HTMLDivElement>(null);
  const isCustom =
    (from !== null || to !== null) &&
    !datePresets(today).some((preset) => preset.from === from && preset.to === to);
  return (
    <div className="flex flex-col gap-3 md:flex-row">
      <div
        className="flex flex-row flex-wrap gap-1 md:w-36 md:flex-col"
        role="group"
        aria-label={copy.filters.dateLabel}
      >
        {datePresets(today).map((preset) => (
          <Button
            key={preset.id}
            variant={preset.from === from && preset.to === to ? "secondary" : "ghost"}
            className="h-8 justify-start max-md:h-11"
            onClick={() => {
              apply({ from: preset.from, to: preset.to });
            }}
          >
            {preset.label}
          </Button>
        ))}
        <Button
          variant={isCustom ? "secondary" : "ghost"}
          className="h-8 justify-start max-md:h-11"
          onClick={() => {
            calendarRef.current
              ?.querySelector<HTMLButtonElement>(".rdp-day_button:not([disabled])")
              ?.focus();
          }}
        >
          {copy.filters.presets.custom}
        </Button>
        <Button
          variant="ghost"
          className="h-8 justify-start max-md:h-11"
          onClick={() => {
            apply({ from: null, to: null });
          }}
        >
          {copy.filters.dateAny}
        </Button>
      </div>
      <div ref={calendarRef} className="flex flex-col gap-2">
        <Suspense
          fallback={
            <Skeleton
              role="status"
              aria-label={copy.filters.calendarLoading}
              className="h-72 w-72 max-w-full"
            />
          }
        >
          <RangeCalendar
            months={months}
            selected={selected}
            defaultMonth={selected?.from ?? today}
            disabled={{ after: today }}
            onSelect={(range) => {
              apply({
                from: range?.from ? iso(range.from) : null,
                to: range?.to ? iso(range.to) : null,
              });
            }}
          />
        </Suspense>
        {error ? (
          <p role="alert" className="text-small text-destructive">
            {error}
          </p>
        ) : null}
      </div>
    </div>
  );
}

export function DateRangeFilter(props: Props) {
  return (
    <Popover>
      <PopoverTrigger
        render={
          <Button variant="outline" className="h-8">
            <CalendarIcon aria-hidden data-icon="inline-start" />
            {rangeLabel(props.from, props.to, props.today)}
            <ChevronDownIcon aria-hidden data-icon="inline-end" />
          </Button>
        }
      />
      <PopoverContent align="start" aria-label={copy.filters.dateLabel} className="w-auto p-3">
        <DateRangePicker {...props} />
      </PopoverContent>
    </Popover>
  );
}
