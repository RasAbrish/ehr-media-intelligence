import { useQuery } from "@tanstack/react-query";

import { copy } from "@/lib/copy";
import { statsQuery } from "@/lib/system-api";

/** "60 patients · 305 searchable records" in the sidebar (docs/06 section 6.1). */
export function StatsPill() {
  const { data } = useQuery(statsQuery());
  if (!data) return null;
  return (
    <p className="hidden border-b px-3 pb-3 text-meta text-muted-foreground tabular-nums sidebar-open:block">
      {copy.stats.pill(data.patients, data.searchable_records)}
    </p>
  );
}
