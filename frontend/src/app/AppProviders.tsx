import { QueryClientProvider, type QueryClient } from "@tanstack/react-query";
import { RouterProvider, type AnyRouter } from "@tanstack/react-router";

import { ThemeProvider } from "@/app/ThemeProvider";
import { AppToaster } from "@/components/common/AppToaster";
import { TooltipProvider } from "@/components/ui/tooltip";

interface AppProvidersProps {
  router: AnyRouter;
  queryClient: QueryClient;
}

export function AppProviders({ router, queryClient }: AppProvidersProps) {
  return (
    <ThemeProvider>
      <QueryClientProvider client={queryClient}>
        <TooltipProvider>
          <RouterProvider router={router} />
          <AppToaster />
        </TooltipProvider>
      </QueryClientProvider>
    </ThemeProvider>
  );
}
