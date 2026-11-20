import { IndexEmptyNotice } from "@/components/common/IndexEmptyNotice";
import { PageHeader } from "@/components/common/PageHeader";
import { copy } from "@/lib/copy";

/** Patient directory shell (P1 in Phase 6). */
export function PatientsPage() {
  return (
    <section className="flex flex-col gap-6">
      <PageHeader title={copy.patients.title} description={copy.patients.body} />
      <IndexEmptyNotice />
    </section>
  );
}
