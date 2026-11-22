import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { RouteError } from "@/components/common/RouteError";
import { copy } from "@/lib/copy";
import { seriousAxeViolations } from "@/test/axe";

it("explains a page that could not be loaded and offers a reload", async () => {
  const user = userEvent.setup();
  const reload = vi.fn();
  const { container } = render(<RouteError onReload={reload} />);
  expect(screen.getByRole("alert")).toHaveTextContent(copy.errors.pageBody);
  await user.click(screen.getByRole("button", { name: copy.errors.reload }));
  expect(reload).toHaveBeenCalledOnce();
  expect(await seriousAxeViolations(container)).toEqual([]);
});
