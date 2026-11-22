import { createMemoryHistory } from "@tanstack/react-router";
import { render, screen } from "@testing-library/react";

import { AppProviders } from "@/app/AppProviders";
import { createApp } from "@/app/create-app";

/** Render the full app at a path and wait for a page to mount. */
export async function renderApp(path = "/") {
  const { router, queryClient } = createApp(createMemoryHistory({ initialEntries: [path] }));
  const view = render(<AppProviders router={router} queryClient={queryClient} />);
  await screen.findByRole("main", { hidden: true }); // hidden while a modal drawer is open
  return { ...view, router, queryClient };
}
