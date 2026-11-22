import { Link } from "@tanstack/react-router";

import { copy } from "@/lib/copy";

export function BrandMark() {
  return (
    <Link
      to="/"
      className="flex min-h-8 items-center gap-2 rounded-md text-heading text-foreground outline-offset-4 max-md:min-h-11 md:min-w-8 md:justify-center md:outline-offset-[-2px] sidebar-open:justify-start sidebar-open:pl-2"
    >
      <span
        aria-hidden="true"
        className="size-3.5 shrink-0 rounded-sm bg-primary md:size-5 sidebar-open:size-3.5"
      />
      <span className="whitespace-nowrap md:sr-only sidebar-open:not-sr-only sidebar-open:whitespace-nowrap">
        {copy.product}
      </span>
    </Link>
  );
}
