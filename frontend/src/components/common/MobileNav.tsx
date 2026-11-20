import { useNavigate, useRouterState } from "@tanstack/react-router";
import { MenuIcon } from "lucide-react";

import { NAV_ITEMS } from "@/components/common/nav-items";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { copy } from "@/lib/copy";

/** Navigation menu for narrow screens (below md), per docs/06 section 7.3. */
export function MobileNav() {
  const navigate = useNavigate();
  const pathname = useRouterState({ select: (state) => state.location.pathname });

  return (
    <div className="md:hidden">
      <DropdownMenu>
        <DropdownMenuTrigger
          render={
            <Button variant="ghost" size="icon" className="size-11" aria-label={copy.nav.menu} />
          }
        >
          <MenuIcon aria-hidden="true" strokeWidth={1.75} />
        </DropdownMenuTrigger>
        <DropdownMenuContent align="start" className="w-48">
          <DropdownMenuRadioGroup
            value={pathname}
            onValueChange={(value: unknown) => {
              const item = NAV_ITEMS.find((candidate) => candidate.to === value);
              if (item) void navigate({ to: item.to });
            }}
          >
            {NAV_ITEMS.map((item) => (
              <DropdownMenuRadioItem key={item.to} value={item.to} className="min-h-11">
                {item.label}
              </DropdownMenuRadioItem>
            ))}
          </DropdownMenuRadioGroup>
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  );
}
