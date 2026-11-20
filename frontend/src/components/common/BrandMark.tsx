import { Link } from "@tanstack/react-router";

import { copy } from "@/lib/copy";

export function BrandMark() {
  return (
    <Link
      to="/"
      className="flex items-center gap-2 rounded-md text-heading text-foreground outline-offset-4"
    >
      <span aria-hidden="true" className="size-3.5 rounded-sm bg-primary" />
      {copy.product}
    </Link>
  );
}
