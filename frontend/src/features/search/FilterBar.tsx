import { SlidersHorizontalIcon, XIcon } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Sheet,
  SheetClose,
  SheetContent,
  SheetFooter,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import { DateRangeFilter, DateRangePicker, rangeLabel } from "@/features/search/DateRangeFilter";
import { activeFilterCount, type FilterValue } from "@/features/search/filters";
import { ResourceTypeFilter, TypeCheckboxes } from "@/features/search/ResourceTypeFilter";
import { copy } from "@/lib/copy";

interface FilterBarProps {
  value: FilterValue;
  onChange: (next: FilterValue) => void;
  today?: Date;
}

/** Type and date filters with removable chips (docs/06 section 6.3); a bottom sheet on mobile. */
export function FilterBar({ value, onChange, today = new Date() }: FilterBarProps) {
  const count = activeFilterCount(value);
  const chips = [
    ...value.types.map((type) => ({
      key: type,
      label: copy.resourceLabels[type],
      remove: () => {
        onChange({ ...value, types: value.types.filter((t) => t !== type) });
      },
    })),
    ...(value.from || value.to
      ? [
          {
            key: "date",
            label: rangeLabel(value.from, value.to, today),
            remove: () => {
              onChange({ ...value, from: null, to: null });
            },
          },
        ]
      : []),
  ];
  const clear = () => {
    onChange({ types: [], from: null, to: null });
  };

  return (
    <div className="flex flex-wrap items-center gap-2">
      <div className="hidden items-center gap-2 md:flex">
        <ResourceTypeFilter
          value={value.types}
          onChange={(types) => {
            onChange({ ...value, types });
          }}
        />
        <DateRangeFilter
          from={value.from}
          to={value.to}
          today={today}
          onChange={(range) => {
            onChange({ ...value, ...range });
          }}
        />
      </div>
      <Sheet>
        <SheetTrigger
          render={
            <Button variant="outline" className="h-11 md:hidden">
              <SlidersHorizontalIcon aria-hidden data-icon="inline-start" />
              {copy.filters.mobileButton(count)}
            </Button>
          }
        />
        <SheetContent side="bottom" className="max-h-[90dvh] overflow-y-auto">
          <SheetHeader>
            <SheetTitle>{copy.filters.label}</SheetTitle>
          </SheetHeader>
          <div className="flex flex-col gap-5 px-4">
            <TypeCheckboxes
              value={value.types}
              onChange={(types) => {
                onChange({ ...value, types });
              }}
            />
            <DateRangePicker
              from={value.from}
              to={value.to}
              today={today}
              months={1}
              onChange={(range) => {
                onChange({ ...value, ...range });
              }}
            />
          </div>
          <SheetFooter>
            <SheetClose render={<Button className="h-11" />}>{copy.filters.done}</SheetClose>
            {count ? (
              <Button variant="ghost" className="h-11" onClick={clear}>
                {copy.filters.clear}
              </Button>
            ) : null}
          </SheetFooter>
        </SheetContent>
      </Sheet>
      {chips.length ? (
        <ul aria-label={copy.filters.active} className="flex flex-wrap items-center gap-1.5">
          {chips.map((chip) => (
            <li key={chip.key}>
              <button
                type="button"
                onClick={chip.remove}
                aria-label={copy.filters.remove(chip.label)}
                className="inline-flex h-8 items-center gap-1 rounded-full bg-secondary px-3 text-meta text-secondary-foreground hover:bg-accent focus-visible:outline-2 focus-visible:outline-ring max-md:h-11"
              >
                {chip.label}
                <XIcon aria-hidden className="size-3.5" />
              </button>
            </li>
          ))}
        </ul>
      ) : null}
      {count ? (
        <Button variant="ghost" className="hidden h-8 md:inline-flex" onClick={clear}>
          {copy.filters.clear}
        </Button>
      ) : null}
    </div>
  );
}
