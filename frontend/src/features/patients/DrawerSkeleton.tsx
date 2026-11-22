import { Skeleton } from "@/components/ui/skeleton";
import { copy } from "@/lib/copy";

export function DrawerSkeleton() {
  return (
    <div role="status" aria-label={copy.drawer.loading} className="flex flex-col gap-3 p-5">
      <Skeleton className="h-6 w-48" />
      <Skeleton className="h-4 w-64" />
      <Skeleton className="mt-4 h-16 w-full" />
      <Skeleton className="h-4 w-1/3" />
      <Skeleton className="h-4 w-2/3" />
      <Skeleton className="h-4 w-1/2" />
    </div>
  );
}
