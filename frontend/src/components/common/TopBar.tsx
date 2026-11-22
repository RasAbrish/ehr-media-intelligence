import { BrandMark } from "@/components/common/BrandMark";
import { MobileNav } from "@/components/common/MobileNav";
import { PrimaryNav } from "@/components/common/PrimaryNav";
import { ShortcutsDialog } from "@/components/common/ShortcutsDialog";
import { StatsPill } from "@/components/common/StatsPill";
import { ThemeToggle } from "@/components/common/ThemeToggle";

/** 56px top bar (docs/06 section 6.1). The stats pill reads GET /stats. */
export function TopBar() {
  return (
    <header className="sticky top-0 z-40 border-b bg-background/80 backdrop-blur supports-[backdrop-filter]:bg-background/70">
      <div className="mx-auto flex h-14 max-w-screen-2xl items-center gap-2 px-3 md:gap-6 md:px-6">
        <MobileNav />
        <BrandMark />
        <PrimaryNav />
        <div className="ml-auto flex items-center gap-1">
          <StatsPill />
          <ThemeToggle />
          <ShortcutsDialog />
        </div>
      </div>
    </header>
  );
}
