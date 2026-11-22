import { useState, useSyncExternalStore } from "react";

import { readStored, writeStored } from "@/lib/storage";

const STORAGE_KEY = "mi-sidebar";
/** Tailwind's lg: from here the sidebar starts open (docs/06 section 6.1). */
const WIDE_QUERY = "(min-width: 64rem)";

function subscribe(onChange: () => void) {
  const query = window.matchMedia(WIDE_QUERY);
  query.addEventListener("change", onChange);
  return () => {
    query.removeEventListener("change", onChange);
  };
}

const isWide = () => window.matchMedia(WIDE_QUERY).matches;

/** Whether the sidebar is open: the stored choice, or the width until there is one. */
export function useSidebar() {
  const wide = useSyncExternalStore(subscribe, isWide);
  const [choice, setChoice] = useState(() => readStored(STORAGE_KEY));
  const open = choice === "open" || (choice !== "closed" && wide);
  const toggle = () => {
    const next = open ? "closed" : "open";
    setChoice(next);
    writeStored(STORAGE_KEY, next);
  };
  return { open, toggle };
}
