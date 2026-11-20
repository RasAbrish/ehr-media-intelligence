import { IndexEmptyNotice } from "@/components/common/IndexEmptyNotice";
import { PageHeader } from "@/components/common/PageHeader";
import { copy } from "@/lib/copy";

/** Search screen shell. Input, filters and results land in Phase 5. */
export function SearchPage() {
  return (
    <section className="flex flex-col gap-6">
      <p className="text-meta text-muted-foreground">{copy.search.pageLabel}</p>
      <PageHeader size="display" title={copy.search.idleTitle} description={copy.search.idleBody} />
      <IndexEmptyNotice />
    </section>
  );
}
