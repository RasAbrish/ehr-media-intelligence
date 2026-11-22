import { Link } from "@tanstack/react-router";

import { copy } from "@/lib/copy";

export function BrandMark() {
  return (
    <Link
      to="/"
      className="flex min-h-8 items-center gap-2 rounded-md text-heading text-foreground outline-offset-4 max-md:min-h-11"
    >
      <span aria-hidden="true" className="size-3.5 rounded-sm bg-primary" />
      {copy.product}
    </Link>
  );
}
