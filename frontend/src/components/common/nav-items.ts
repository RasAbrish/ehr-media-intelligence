import { copy } from "@/lib/copy";

export const NAV_ITEMS = [
  { to: "/", label: copy.nav.search },
  { to: "/patients", label: copy.nav.patients },
  { to: "/quality", label: copy.nav.quality },
] as const;

export type NavPath = (typeof NAV_ITEMS)[number]["to"];
