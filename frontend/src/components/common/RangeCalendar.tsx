import { DayPicker, type DateRange, type Matcher } from "react-day-picker";

import { copy } from "@/lib/copy";
import { cn } from "@/lib/utils";

const DAY = new Intl.DateTimeFormat("en-US", { dateStyle: "full" });

interface RangeCalendarProps {
  selected: DateRange | undefined;
  onSelect: (range: DateRange | undefined) => void;
  months?: number;
  defaultMonth?: Date;
  disabled?: Matcher;
  className?: string;
}

/**
 * Range calendar on react-day-picker, themed with the app tokens. A range picker cannot
 * produce an end before its start, which is how the date filter prevents invalid ranges.
 */
export function RangeCalendar({
  selected,
  onSelect,
  months = 2,
  defaultMonth,
  disabled,
  className,
}: RangeCalendarProps) {
  return (
    <DayPicker
      mode="range"
      numberOfMonths={months}
      selected={selected}
      onSelect={onSelect}
      showOutsideDays
      labels={{
        // The default "26th" does not contain the visible "26" (WCAG 2.5.3, label in name).
        labelDayButton: (date, modifiers) =>
          copy.filters.day(DAY.format(date), modifiers.today, modifiers.selected),
      }}
      {...(defaultMonth ? { defaultMonth } : {})}
      {...(disabled ? { disabled } : {})}
      className={cn(
        "text-small [--rdp-accent-background-color:var(--accent)] [--rdp-accent-color:var(--primary)]",
        "[--rdp-day-height:2.25rem] [--rdp-day-width:2.25rem] [--rdp-day_button-height:2rem] [--rdp-day_button-width:2rem]",
        "[--rdp-day_button-border-radius:var(--radius-md)] [--rdp-months-gap:1.5rem] [--rdp-nav-height:2.25rem]",
        "[--rdp-range_end-color:var(--primary-foreground)] [--rdp-range_start-color:var(--primary-foreground)]",
        // 44 px days and arrows on touch layouts (docs/06 section 9).
        "max-md:[--rdp-day-height:2.75rem] max-md:[--rdp-day-width:2.75rem] max-md:[--rdp-day_button-height:2.75rem] max-md:[--rdp-day_button-width:2.75rem]",
        "max-md:[--rdp-nav-height:2.75rem] max-md:[--rdp-nav_button-height:2.75rem] max-md:[--rdp-nav_button-width:2.75rem]",
        "[--rdp-today-color:var(--primary)] [&_.rdp-caption_label]:text-heading",
        className,
      )}
    />
  );
}
