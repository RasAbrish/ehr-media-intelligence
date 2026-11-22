import { Link } from "@tanstack/react-router";

import { NAV_ITEMS, SIDEBAR_ITEM } from "@/components/common/nav-items";
import { copy } from "@/lib/copy";
import { cn } from "@/lib/utils";

/** Sidebar navigation (md and up). Active item: accent fill and the 3px rule of a selected card. */
export function PrimaryNav() {
  return (
    <nav aria-label={copy.nav.label} className="hidden md:block">
      <ul className="flex flex-col gap-1">
        {NAV_ITEMS.map(({ to, label, Icon }) => (
          <li key={to}>
            <Link
              to={to}
              activeOptions={{ exact: to === "/", includeSearch: false }}
              className={cn(
                "group/nav flex items-center rounded-lg text-muted-foreground outline-offset-[-2px] transition-colors duration-120 hover:bg-muted hover:text-foreground",
                "data-[status=active]:bg-accent data-[status=active]:text-accent-foreground data-[status=active]:shadow-[inset_3px_0_0_var(--primary)]",
                SIDEBAR_ITEM,
              )}
            >
              <Icon
                aria-hidden="true"
                strokeWidth={1.75}
                className="size-5 shrink-0 group-data-[status=active]/nav:text-primary"
              />
              <span>{label}</span>
            </Link>
          </li>
        ))}
      </ul>
    </nav>
  );
}
