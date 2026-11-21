import {
  createRootRoute,
  createRoute,
  createRouter,
  type RouterHistory,
} from "@tanstack/react-router";

import { AppShell } from "@/app/AppShell";
import { parseSearchParams, type SearchPageParams } from "@/features/search/search-params";
import { NotFoundPage } from "@/routes/NotFoundPage";
import { PatientsPage } from "@/routes/PatientsPage";
import { QualityPage } from "@/routes/QualityPage";
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
  component: PatientsPage,
});

const qualityRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/quality",
  component: QualityPage,
});

const routeTree = rootRoute.addChildren([searchRoute, patientsRoute, qualityRoute]);

export function createAppRouter(history?: RouterHistory) {
  return createRouter({
    routeTree,
    defaultPreload: "intent",
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
