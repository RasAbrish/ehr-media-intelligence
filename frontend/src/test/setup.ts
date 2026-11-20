import "@testing-library/jest-dom/vitest";

import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

afterEach(() => {
  cleanup();
  document.documentElement.className = "";
  window.localStorage.clear();
});

// jsdom has no matchMedia; default to a light system theme.
if (typeof window.matchMedia !== "function") {
  Object.defineProperty(window, "matchMedia", {
    writable: true,
    value: (query: string): MediaQueryList => {
      const list: Partial<MediaQueryList> = {
        matches: false,
        media: query,
        onchange: null,
        addEventListener: () => undefined,
        removeEventListener: () => undefined,
        dispatchEvent: () => false,
      };
      return list as MediaQueryList;
    },
  });
}

// jsdom does not implement scrolling; the router's scroll restoration calls it.
window.scrollTo = () => undefined;
