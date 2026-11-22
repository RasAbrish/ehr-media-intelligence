import {
  createRootRoute,
  createRoute,
  createRouter,
  lazyRouteComponent,
  type RouterHistory,
} from "@tanstack/react-router";

import { AppShell } from "@/app/AppShell";
import { RouteError } from "@/components/common/RouteError";
import { RoutePending } from "@/components/common/RoutePending";
import {
  parseDirectoryParams,
  type DirectoryPageParams,
} from "@/features/patients/directory-params";
import { parseQualityParams, type QualityPageParams } from "@/features/quality/quality-params";
import { parseSearchParams, type SearchPageParams } from "@/features/search/search-params";
import { NotFoundPage } from "@/routes/NotFoundPage";
import { SearchPage } from "@/routes/SearchPage";

const rootRoute = createRootRoute({
  component: AppShell,
  notFoundComponent: NotFoundPage,
});

const searchRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/",
  validateSearch: (search: Record<string, unknown>): SearchPageParams => parseSearchParams(search),
  component: SearchPage,
});

const patientsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/patients",
  validateSearch: (search: Record<string, unknown>): DirectoryPageParams =>
    parseDirectoryParams(search),
  component: lazyRouteComponent(() => import("@/routes/PatientsPage"), "PatientsPage"),
});

const qualityRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/quality",
  validateSearch: (search: Record<string, unknown>): QualityPageParams =>
    parseQualityParams(search),
  component: lazyRouteComponent(() => import("@/routes/QualityPage"), "QualityPage"),
});

const routeTree = rootRoute.addChildren([searchRoute, patientsRoute, qualityRoute]);

export function createAppRouter(history?: RouterHistory) {
  return createRouter({
    routeTree,
    defaultPreload: "intent",
    defaultPendingComponent: RoutePending,
    defaultErrorComponent: () => <RouteError />,
    scrollRestoration: true,
    ...(history ? { history } : {}),
  });
}

export const router = createAppRouter();

declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}
