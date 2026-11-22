import { Outlet } from "@tanstack/react-router";
import type { ReactNode } from "react";

import { DemoBanner } from "@/components/common/DemoBanner";
import { Sidebar } from "@/components/common/Sidebar";
import { useSearchShortcut } from "@/hooks/useSearchShortcut";
import { useSidebar } from "@/hooks/useSidebar";
import { copy } from "@/lib/copy";
import { cn } from "@/lib/utils";

/** The signed-in layout. `children` replaces the page outlet (the not-found page). */
export function AppShell({ children }: { children?: ReactNode }) {
  useSearchShortcut();
  const { open, toggle } = useSidebar();
  return (
    <div
      data-sidebar={open ? "open" : "closed"}
      className={cn("flex min-h-dvh flex-col", open ? "md:pl-56" : "md:pl-20")}
    >
      <a
        href="#main"
        className="sr-only z-50 rounded-md bg-primary text-primary-foreground focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:px-3 focus:py-2 max-md:focus:py-3"
      >
        {copy.skipLink}
      </a>
      {import.meta.env.VITE_DEMO_MODE === "true" ? <DemoBanner /> : null}
      <Sidebar open={open} onToggle={toggle} />
      <main id="main" tabIndex={-1} className="min-w-0 flex-1 outline-none">
        <div className="w-full px-4 py-6 md:px-6 md:py-8 2xl:px-8">{children ?? <Outlet />}</div>
      </main>
    </div>
  );
}
