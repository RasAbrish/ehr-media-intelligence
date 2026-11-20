import { QueryClientProvider, type QueryClient } from "@tanstack/react-query";
import { RouterProvider, type AnyRouter } from "@tanstack/react-router";

import { ThemeProvider } from "@/app/ThemeProvider";

interface AppProvidersProps {
  router: AnyRouter;
  queryClient: QueryClient;
}

export function AppProviders({ router, queryClient }: AppProvidersProps) {
  return (
    <ThemeProvider>
      <QueryClientProvider client={queryClient}>
        <RouterProvider router={router} />
      </QueryClientProvider>
    </ThemeProvider>
  );
}
