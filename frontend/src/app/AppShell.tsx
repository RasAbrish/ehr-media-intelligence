import { Outlet } from "@tanstack/react-router";

import { TopBar } from "@/components/common/TopBar";
import { useSearchShortcut } from "@/hooks/useSearchShortcut";
import { copy } from "@/lib/copy";

export function AppShell() {
  useSearchShortcut();
  return (
    <div className="flex min-h-dvh flex-col">
      <a
        href="#main"
        className="sr-only z-50 rounded-md bg-primary text-primary-foreground focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:px-3 focus:py-2 max-md:focus:py-3"
      >
        {copy.skipLink}
      </a>
      <TopBar />
      <main id="main" tabIndex={-1} className="flex-1 outline-none">
        <div className="mx-auto w-full max-w-280 px-4 py-8 md:px-6 md:py-12">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
