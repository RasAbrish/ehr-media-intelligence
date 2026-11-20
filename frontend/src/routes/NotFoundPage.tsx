import { Link } from "@tanstack/react-router";

import { PageHeader } from "@/components/common/PageHeader";
import { buttonVariants } from "@/components/ui/button";
import { copy } from "@/lib/copy";

export function NotFoundPage() {
  return (
    <section className="flex flex-col items-start gap-4">
      <PageHeader title={copy.notFound.title} description={copy.notFound.body} />
      <Link to="/" className={buttonVariants({ variant: "outline" })}>
        {copy.notFound.action}
      </Link>
    </section>
  );
}
