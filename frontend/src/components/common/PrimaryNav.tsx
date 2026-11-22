import { Link } from "@tanstack/react-router";

import { NAV_ITEMS } from "@/components/common/nav-items";
import { copy } from "@/lib/copy";

/** Desktop navigation (md and up). Active item: foreground text with a 2px primary indicator. */
export function PrimaryNav() {
  return (
    <nav aria-label={copy.nav.label} className="hidden h-full md:block">
      <ul className="flex h-full items-stretch gap-1">
        {NAV_ITEMS.map((item) => (
          <li key={item.to} className="flex">
            <Link
              to={item.to}
              activeOptions={{ exact: item.to === "/", includeSearch: false }}
              className="relative flex items-center rounded-md px-3 text-muted-foreground outline-offset-[-2px] transition-colors duration-120 hover:text-foreground data-[status=active]:text-foreground data-[status=active]:after:absolute data-[status=active]:after:inset-x-3 data-[status=active]:after:bottom-0 data-[status=active]:after:h-0.5 data-[status=active]:after:rounded-full data-[status=active]:after:bg-primary"
            >
              {item.label}
            </Link>
          </li>
        ))}
      </ul>
    </nav>
  );
}
