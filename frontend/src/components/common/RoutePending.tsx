import { Skeleton } from "@/components/ui/skeleton";
import { copy } from "@/lib/copy";

/** Shown when a page chunk takes long to arrive. */
export function RoutePending() {
  return (
    <div role="status" aria-label={copy.loadingPage} className="flex flex-col gap-4">
      <Skeleton className="h-7 w-48" />
      <Skeleton className="h-64 w-full" />
    </div>
  );
}
