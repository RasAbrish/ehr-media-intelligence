import type { Decorator, Preview } from "@storybook/react-vite";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createMemoryHistory, RouterContextProvider } from "@tanstack/react-router";
import { useEffect, useMemo, useState, type ReactNode } from "react";

import "@/index.css";
import { ThemeContext } from "@/app/theme-context";
import { TooltipProvider } from "@/components/ui/tooltip";
import { createAppRouter } from "@/router";
import { seedQueryClient } from "@/test/seed-query-client";

/** Stories never reach the network: data-fetching components read a seeded cache. */
function Providers({ dark, children }: { dark: boolean; children: ReactNode }) {
  useEffect(() => {
    document.documentElement.classList.toggle("dark", dark);
  }, [dark]);
  const [client] = useState(() => {
    const seeded = new QueryClient({
      defaultOptions: { queries: { retry: false, staleTime: Infinity } },
    });
    seedQueryClient(seeded);
    return seeded;
  });
  // Links and the navigation need a router; the toolbar owns the theme.
  const [router] = useState(() => createAppRouter(createMemoryHistory()));
  const theme = useMemo(
    () => ({
      preference: dark ? ("dark" as const) : ("light" as const),
      resolved: dark ? ("dark" as const) : ("light" as const),
      setPreference: () => undefined,
    }),
    [dark],
  );
  return (
    <QueryClientProvider client={client}>
      <TooltipProvider>
        <ThemeContext value={theme}>
          <RouterContextProvider router={router}>
            <div className="min-h-dvh bg-background p-4 text-foreground">{children}</div>
          </RouterContextProvider>
        </ThemeContext>
      </TooltipProvider>
    </QueryClientProvider>
  );
}

const withProviders: Decorator = (Story, context) => (
  <Providers dark={context.globals.theme === "dark"}>
    <Story />
  </Providers>
);

const preview: Preview = {
  decorators: [withProviders],
  globalTypes: {
    theme: {
      description: "Color theme",
      toolbar: { title: "Theme", icon: "mirror", items: ["light", "dark"], dynamicTitle: true },
    },
  },
  initialGlobals: { theme: "light" },
  parameters: { a11y: { test: "error" }, layout: "fullscreen" },
};

export default preview;
