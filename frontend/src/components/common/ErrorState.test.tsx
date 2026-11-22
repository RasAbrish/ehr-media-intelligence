import { render, screen } from "@testing-library/react";

import { ErrorState } from "@/components/common/ErrorState";
import { copy } from "@/lib/copy";
import { ApiError } from "@/lib/problem";
import { fixtures } from "@/test/msw/fixtures";

it.each([400, 403, 405, 413])("never shows backend text for a %i (gap 14)", (status) => {
  const detail = "sqlite: no such column xyz";
  render(
    <ErrorState
      error={new ApiError(status, { ...fixtures.problem, status, code: "other", detail })}
    />,
  );
  expect(screen.getByText(copy.errors.request)).toBeInTheDocument();
  expect(screen.queryByText(detail)).toBeNull();
});
