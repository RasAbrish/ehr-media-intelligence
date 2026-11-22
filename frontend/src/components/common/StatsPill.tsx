import { useQuery } from "@tanstack/react-query";

import { copy } from "@/lib/copy";
import { statsQuery } from "@/lib/system-api";

/** "60 patients · 305 searchable records" in the top bar (docs/06 section 6.1). */
export function StatsPill() {
  const { data } = useQuery(statsQuery());
  if (!data) return null;
  return (
    <p className="hidden rounded-full border px-3 py-1 text-meta whitespace-nowrap text-muted-foreground tabular-nums lg:block">
      {copy.stats.pill(data.patients, data.searchable_records)}
    </p>
  );
}
