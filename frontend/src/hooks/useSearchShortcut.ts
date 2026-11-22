import { useNavigate } from "@tanstack/react-router";
import { useEffect } from "react";

import { focusPageSearch, isTypingTarget } from "@/lib/keyboard";
import { modalOpen } from "@/lib/modal";

/** "/" and Ctrl/Cmd+K focus search from anywhere (docs/06 section 8.4). */
export function useSearchShortcut(): void {
  const navigate = useNavigate();
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (modalOpen()) return; // the drawer and dialogs keep focus while open
      const commandK = (event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k";
      if (!commandK && (event.key !== "/" || isTypingTarget(event.target))) return;
      event.preventDefault();
      if (focusPageSearch()) return;
      // No field on this page: open search, then focus once it has rendered.
      void navigate({ to: "/" }).then(() => requestAnimationFrame(() => void focusPageSearch()));
    };
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("keydown", onKey);
    };
  }, [navigate]);
}
