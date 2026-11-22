import { useQuery } from "@tanstack/react-query";
import { LogOutIcon, PanelLeftCloseIcon, PanelLeftOpenIcon } from "lucide-react";

import { BrandMark } from "@/components/common/BrandMark";
import { SIDEBAR_ITEM } from "@/components/common/nav-items";
import { MobileNav } from "@/components/common/MobileNav";
import { PrimaryNav } from "@/components/common/PrimaryNav";
import { ShortcutsDialog } from "@/components/common/ShortcutsDialog";
import { StatsPill } from "@/components/common/StatsPill";
import { ThemeToggle } from "@/components/common/ThemeToggle";
import { Button } from "@/components/ui/button";
import { meQuery } from "@/features/auth/api";
import { useSignOut } from "@/features/auth/useSignOut";
import { copy } from "@/lib/copy";
import { cn } from "@/lib/utils";

interface SidebarProps {
  open: boolean;
  onToggle: () => void;
}

/** docs/06 section 6.1: a top bar below md, else a labeled sidebar or an icon rail. */
export function Sidebar({ open, onToggle }: SidebarProps) {
  const ToggleIcon = open ? PanelLeftCloseIcon : PanelLeftOpenIcon;
  const toggleLabel = open ? copy.nav.close : copy.nav.open;
  const user = useQuery({ ...meQuery(), enabled: false }).data;
  const signOut = useSignOut();
  return (
    <header className="sticky top-0 z-40 flex h-14 shrink-0 items-center gap-2 border-b bg-background/80 px-3 backdrop-blur md:fixed md:inset-y-0 md:left-0 md:h-auto md:w-20 md:flex-col md:items-stretch md:gap-6 md:overflow-y-auto md:border-r md:border-b-0 md:bg-card md:px-2 md:py-4 md:backdrop-blur-none sidebar-open:w-56 sidebar-open:px-3">
      <MobileNav />
      <div className="flex items-center gap-1 md:flex-col sidebar-open:flex-row sidebar-open:justify-between">
        <BrandMark />
        <Button
          variant="ghost"
          size="icon"
          className="hidden size-8 shrink-0 text-muted-foreground aria-expanded:bg-transparent aria-expanded:hover:bg-muted md:inline-flex pointer-coarse:size-11"
          aria-label={toggleLabel}
          aria-expanded={open}
          title={toggleLabel}
          onClick={onToggle}
        >
          <ToggleIcon aria-hidden="true" strokeWidth={1.75} className="size-5" />
        </Button>
      </div>
      <PrimaryNav />
      <div className="ml-auto flex items-center gap-1 md:mt-auto md:ml-0 md:flex-col md:items-stretch">
        <StatsPill />
        {user ? (
          <p className="hidden px-3 text-meta wrap-anywhere text-muted-foreground sidebar-open:block">
            {copy.auth.signedInAs(user.display_name)}
          </p>
        ) : null}
        <ThemeToggle />
        <ShortcutsDialog />
        <Button
          variant="ghost"
          size="icon"
          className={cn("hidden font-normal text-muted-foreground md:inline-flex", SIDEBAR_ITEM)}
          disabled={signOut.isPending}
          onClick={() => {
            signOut.mutate();
          }}
        >
          <LogOutIcon aria-hidden="true" strokeWidth={1.75} className="size-5" />
          <span>{copy.auth.signOut}</span>
        </Button>
      </div>
    </header>
  );
}
