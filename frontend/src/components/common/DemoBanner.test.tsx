import { QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { delay, http, HttpResponse } from "msw";

import { createQueryClient } from "@/app/queryClient";
import { DemoBanner } from "@/components/common/DemoBanner";
import { copy } from "@/lib/copy";
import { server } from "@/test/msw/server";

function renderBanner() {
  const client = createQueryClient();
  const invalidate = vi.spyOn(client, "invalidateQueries");
  render(
    <QueryClientProvider client={client}>
      <DemoBanner pollMs={50} />
    </QueryClientProvider>,
  );
  return invalidate;
}

it("always says the demo is synthetic and takes no patient data", async () => {
  server.use(http.get("*/api/health", () => HttpResponse.json({ status: "ok", version: "1" })));
  renderBanner();
  expect(await screen.findByText(copy.demo.notice)).toBeInTheDocument();
});

it("says the free server is waking, then reloads the page data", async () => {
  let awake = false;
  server.use(
    http.get("*/api/health", () =>
      // While it wakes, Render answers with an HTML loading page.
      awake
        ? HttpResponse.json({ status: "ok", version: "1" })
        : HttpResponse.html("<html>waking</html>"),
    ),
  );
  const invalidate = renderBanner();
  expect(await screen.findByText(copy.demo.waking)).toBeInTheDocument();
  expect(invalidate).not.toHaveBeenCalled();
  awake = true;
  await vi.waitFor(() => {
    expect(screen.queryByText(copy.demo.waking)).toBeNull();
  });
  expect(invalidate).toHaveBeenCalled();
});

it("does not say waking during a normal page load", async () => {
  server.use(
    http.get("*/api/health", async () => {
      await delay(150);
      return HttpResponse.json({ status: "ok", version: "1" });
    }),
  );
  renderBanner();
  expect(await screen.findByText(copy.demo.notice)).toBeInTheDocument();
  expect(screen.queryByText(copy.demo.waking)).toBeNull();
});

it("says waking when the host holds the request", async () => {
  server.use(http.get("*/api/health", () => delay("infinite")));
  renderBanner();
  expect(await screen.findByText(copy.demo.waking, {}, { timeout: 3000 })).toBeInTheDocument();
});
