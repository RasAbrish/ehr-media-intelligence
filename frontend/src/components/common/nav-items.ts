import { ClipboardCheckIcon, SearchIcon, UsersIcon } from "lucide-react";

import { copy } from "@/lib/copy";

export const NAV_ITEMS = [
  { to: "/", label: copy.nav.search, Icon: SearchIcon },
  { to: "/patients", label: copy.nav.patients, Icon: UsersIcon },
  { to: "/quality", label: copy.nav.quality, Icon: ClipboardCheckIcon },
] as const;

/** A sidebar entry: icon over label on the rail, icon beside label in the full sidebar. */
export const SIDEBAR_ITEM =
  "md:h-auto md:min-h-14 md:w-full md:flex-col md:justify-center md:gap-1 md:px-1 md:py-2 md:text-center md:text-meta md:whitespace-normal sidebar-open:min-h-10 sidebar-open:flex-row sidebar-open:justify-start sidebar-open:gap-3 sidebar-open:px-3 sidebar-open:text-left sidebar-open:text-body pointer-coarse:min-h-11";

export type NavPath = (typeof NAV_ITEMS)[number]["to"];
