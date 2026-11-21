import { ChevronDownIcon } from "lucide-react";
import { useId } from "react";

import { TYPE_DOT } from "@/components/common/ResourceTypeBadge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { FILTER_TYPES, typeSummary } from "@/features/search/filters";
import type { SearchableType } from "@/lib/contract-enums";
import { copy } from "@/lib/copy";
import { cn } from "@/lib/utils";

interface Props {
  value: SearchableType[];
  onChange: (next: SearchableType[]) => void;
}

/** Checkbox list with colored dots; shared by the popover and the mobile sheet. */
export function TypeCheckboxes({ value, onChange }: Props) {
  const groupId = useId();
  const toggle = (type: SearchableType, checked: boolean) => {
    onChange(
      checked
        ? FILTER_TYPES.filter((t) => t === type || value.includes(t))
        : value.filter((t) => t !== type),
    );
  };
  return (
    <fieldset className="flex flex-col gap-1">
      <legend className="mb-1 text-meta text-muted-foreground">{copy.filters.typeLabel}</legend>
      {FILTER_TYPES.map((type) => {
        const id = `${groupId}-${type}`;
        return (
          <label
            key={type}
            htmlFor={id}
            className="flex min-h-8 cursor-pointer items-center gap-2.5 rounded-md px-1.5 hover:bg-accent/50"
          >
            <Checkbox
              id={id}
              checked={value.includes(type)}
              onCheckedChange={(checked) => {
                toggle(type, checked);
              }}
            />
            <span aria-hidden className={cn("size-1.5 rounded-full", TYPE_DOT[type])} />
            <span className="text-body">{copy.resourceLabels[type]}</span>
          </label>
        );
      })}
    </fieldset>
  );
}

export function ResourceTypeFilter({ value, onChange }: Props) {
  return (
    <Popover>
      <PopoverTrigger
        render={
          <Button variant="outline" className="h-8">
            {copy.filters.typeButton(typeSummary(value))}
            <ChevronDownIcon aria-hidden data-icon="inline-end" />
          </Button>
        }
      />
      <PopoverContent align="start" className="w-60 p-2">
        <TypeCheckboxes value={value} onChange={onChange} />
      </PopoverContent>
    </Popover>
  );
}
