import type { QueryClient } from "@tanstack/react-query";
import {
  createRootRouteWithContext,
  createRoute,
  createRouter,
  lazyRouteComponent,
  Outlet,
  redirect,
  type RouterHistory,
} from "@tanstack/react-router";

import { AppShell } from "@/app/AppShell";
import { createQueryClient } from "@/app/queryClient";
import { RouteError } from "@/components/common/RouteError";
import { RoutePending } from "@/components/common/RoutePending";
import { meQuery, safeNext } from "@/features/auth/api";
import type { CurrentUser } from "@/features/auth/schemas";
import {
  parseDirectoryParams,
  type DirectoryPageParams,
} from "@/features/patients/directory-params";
import { parseQualityParams, type QualityPageParams } from "@/features/quality/quality-params";
import { parseSearchParams, type SearchPageParams } from "@/features/search/search-params";
import { ApiError } from "@/lib/problem";
import { NotFoundPage } from "@/routes/NotFoundPage";
import { SearchPage } from "@/routes/SearchPage";

interface RouterContext {
  queryClient: QueryClient;
}

/** The user, `null` when signed out, `undefined` when the API cannot say (asleep, offline). */
async function currentUser(client: QueryClient): Promise<CurrentUser | null | undefined> {
  const known = client.getQueryData<CurrentUser | null>(meQuery().queryKey);
  if (known !== undefined) return known;
  try {
    return await client.query(meQuery());
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) return null;
    return undefined; // the data pages show their own errors, and the demo banner waits
  }
}

const rootRoute = createRootRouteWithContext<RouterContext>()({
  component: Outlet,
  // An unknown path matches no layout, so the shell is drawn here around the message.
  notFoundComponent: () => (
    <AppShell>
      <NotFoundPage />
    </AppShell>
  ),
});

export interface SignInParams {
  next?: string;
}

const signInRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/signin",
  validateSearch: (search: Record<string, unknown>): SignInParams =>
    search.next === undefined ? {} : { next: safeNext(search.next) },
  beforeLoad: async ({ context, search }) => {
    if (await currentUser(context.queryClient)) {
      // eslint-disable-next-line @typescript-eslint/only-throw-error -- TanStack Router redirects by throwing
      throw redirect({ href: safeNext(search.next) });
    }
  },
  component: lazyRouteComponent(() => import("@/routes/SignInPage"), "SignInPage"),
});

/** Every other page needs a session (docs/04 section 3a). */
const appRoute = createRoute({
  getParentRoute: () => rootRoute,
  id: "_app",
  beforeLoad: async ({ context, location }) => {
    if ((await currentUser(context.queryClient)) === null) {
      // eslint-disable-next-line @typescript-eslint/only-throw-error -- TanStack Router redirects by throwing
      throw redirect({ to: "/signin", search: { next: location.href } });
    }
  },
  component: AppShell,
});

const searchRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/",
  validateSearch: (search: Record<string, unknown>): SearchPageParams => parseSearchParams(search),
  component: SearchPage,
});

const patientsRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/patients",
  validateSearch: (search: Record<string, unknown>): DirectoryPageParams =>
    parseDirectoryParams(search),
  component: lazyRouteComponent(() => import("@/routes/PatientsPage"), "PatientsPage"),
});

const qualityRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/quality",
  validateSearch: (search: Record<string, unknown>): QualityPageParams =>
    parseQualityParams(search),
  component: lazyRouteComponent(() => import("@/routes/QualityPage"), "QualityPage"),
});

const routeTree = rootRoute.addChildren([
  signInRoute,
  appRoute.addChildren([searchRoute, patientsRoute, qualityRoute]),
]);

export function createAppRouter(
  history?: RouterHistory,
  queryClient: QueryClient = createQueryClient(),
) {
  return createRouter({
    routeTree,
    context: { queryClient },
    defaultPreload: "intent",
    defaultPendingComponent: RoutePending,
    defaultErrorComponent: () => <RouteError />,
    scrollRestoration: true,
    ...(history ? { history } : {}),
  });
}

declare module "@tanstack/react-router" {
  interface Register {
    router: ReturnType<typeof createAppRouter>;
  }
}
