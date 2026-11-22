import { useId } from "react";

import { SearchSortSchema, type SearchSort } from "@/lib/contract-enums";
import { copy } from "@/lib/copy";

interface SortSelectProps {
  value: SearchSort;
  onChange: (next: SearchSort) => void;
}

/** Result order (docs/06 section 6.4): relevance, or newest with every search word. */
export function SortSelect({ value, onChange }: SortSelectProps) {
  const id = useId();
  return (
    <div className="flex items-center gap-2">
      <label htmlFor={id} className="text-meta text-muted-foreground">
        {copy.sort.label}
      </label>
      <select
        id={id}
        value={value}
        onChange={(event) => {
          onChange(SearchSortSchema.parse(event.target.value));
        }}
        className="h-8 rounded-lg border border-input bg-card px-2 text-small text-foreground focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/25 focus-visible:outline-none max-md:h-11"
      >
        {SearchSortSchema.options.map((option) => (
          <option key={option} value={option}>
            {copy.sort.options[option]}
          </option>
        ))}
      </select>
    </div>
  );
}
