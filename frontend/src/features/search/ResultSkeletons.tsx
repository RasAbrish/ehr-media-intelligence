import { Skeleton } from "@/components/ui/skeleton";
import { copy } from "@/lib/copy";

/**
 * Five skeleton cards mirroring the card layout, so nothing shifts when results land.
 * They fade in after 150 ms, so fast responses never flash a skeleton (docs/06 section 13).
 */
export function ResultSkeletons() {
  return (
    <div
      role="status"
      aria-label={copy.search.loading}
      className="flex animate-in flex-col gap-2 delay-150 duration-150 fill-mode-both fade-in"
    >
      {Array.from({ length: 5 }, (_, index) => (
        <div key={index} className="flex flex-col gap-2.5 rounded-xl border bg-card p-3 md:p-4">
          <div className="flex items-center gap-3">
            <Skeleton className="h-4 w-36" />
            <Skeleton className="h-3.5 w-24" />
            <Skeleton className="ml-auto h-3.5 w-16" />
          </div>
          <div className="flex items-center gap-2">
            <Skeleton className="h-5 w-28" />
            <Skeleton className="h-3.5 w-48" />
          </div>
          <Skeleton className="h-3.5 w-full" />
          <Skeleton className="h-3.5 w-2/3" />
        </div>
      ))}
    </div>
  );
}
