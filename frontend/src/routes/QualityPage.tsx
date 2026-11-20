import { IndexEmptyNotice } from "@/components/common/IndexEmptyNotice";
import { PageHeader } from "@/components/common/PageHeader";
import { copy } from "@/lib/copy";

/** Data quality shell (P1 in Phase 6). */
export function QualityPage() {
  return (
    <section className="flex flex-col gap-6">
      <PageHeader title={copy.quality.title} description={copy.quality.body} />
      <IndexEmptyNotice />
    </section>
  );
}
