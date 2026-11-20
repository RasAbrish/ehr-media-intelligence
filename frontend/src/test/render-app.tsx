import { createMemoryHistory } from "@tanstack/react-router";
import { render, screen } from "@testing-library/react";

import { AppProviders } from "@/app/AppProviders";
import { createQueryClient } from "@/app/queryClient";
import { createAppRouter } from "@/router";

/** Render the full app at a path and wait for the shell to mount. */
export async function renderApp(path = "/") {
  const router = createAppRouter(createMemoryHistory({ initialEntries: [path] }));
  const view = render(<AppProviders router={router} queryClient={createQueryClient()} />);
  await screen.findByRole("banner");
  return { ...view, router };
}
