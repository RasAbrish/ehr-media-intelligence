import { DayPicker, type DateRange, type Matcher } from "react-day-picker";
import "react-day-picker/style.css";

import { cn } from "@/lib/utils";

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
      {...(defaultMonth ? { defaultMonth } : {})}
      {...(disabled ? { disabled } : {})}
      className={cn(
        "text-small [--rdp-accent-background-color:var(--accent)] [--rdp-accent-color:var(--primary)]",
        "[--rdp-day-height:2.25rem] [--rdp-day-width:2.25rem] [--rdp-day_button-height:2rem] [--rdp-day_button-width:2rem]",
        "[--rdp-day_button-border-radius:var(--radius-md)] [--rdp-months-gap:1.5rem] [--rdp-nav-height:2.25rem]",
        "[--rdp-range_end-color:var(--primary-foreground)] [--rdp-range_start-color:var(--primary-foreground)]",
        "[--rdp-today-color:var(--primary)] [&_.rdp-caption_label]:text-heading",
        className,
      )}
    />
  );
}
