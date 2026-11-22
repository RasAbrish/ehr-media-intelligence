import type { RouterHistory } from "@tanstack/react-router";

import { createQueryClient } from "@/app/queryClient";
import { keys } from "@/lib/query-keys";
import { createAppRouter } from "@/router";

/** The router and query client, wired so an ended session returns to sign-in. */
export function createApp(history?: RouterHistory) {
  const queryClient = createQueryClient(() => {
    const { pathname, href } = router.state.location;
    if (pathname === "/signin") return;
    queryClient.clear(); // no patient data stays in memory after a session ends
    queryClient.setQueryData(keys.me, null);
    void router.navigate({ to: "/signin", search: { next: href } });
  });
  const router = createAppRouter(history, queryClient);
  return { router, queryClient };
}
