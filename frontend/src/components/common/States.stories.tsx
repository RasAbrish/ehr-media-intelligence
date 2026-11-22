import type { Meta, StoryObj } from "@storybook/react-vite";

import { EmptyState } from "@/components/common/EmptyState";
import { ErrorState } from "@/components/common/ErrorState";
import { IndexEmptyNotice } from "@/components/common/IndexEmptyNotice";
import { RouteError } from "@/components/common/RouteError";
import { RoutePending } from "@/components/common/RoutePending";
import { Button } from "@/components/ui/button";
import { copy } from "@/lib/copy";
import { ApiError, NetworkError } from "@/lib/problem";
import { fixtures } from "@/test/msw/fixtures";

const meta: Meta = { title: "Common/States" };
export default meta;

export const NoResults: StoryObj = {
  render: () => (
    <EmptyState
      title={copy.search.noResultsTitle}
      description={copy.search.noResultsBody}
      action={<Button variant="outline">{copy.filters.clear}</Button>}
    />
  ),
};

export const ServerError: StoryObj = {
  render: () => (
    <ErrorState
      error={new ApiError(500, { ...fixtures.problem, status: 500, code: "internal_error" })}
      onRetry={() => undefined}
    />
  ),
};

export const NetworkDown: StoryObj = {
  render: () => <ErrorState error={new NetworkError(null)} onRetry={() => undefined} />,
};

export const PageFailed: StoryObj = { render: () => <RouteError onReload={() => undefined} /> };

export const PageLoading: StoryObj = { render: () => <RoutePending /> };

export const IndexEmpty: StoryObj = { render: () => <IndexEmptyNotice /> };
