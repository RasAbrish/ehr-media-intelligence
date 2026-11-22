import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";

import { FilterBar } from "@/features/search/FilterBar";
import type { FilterValue } from "@/features/search/filters";
import { copy } from "@/lib/copy";
import { seriousAxeViolations } from "@/test/axe";
import { must } from "@/test/must";

const TODAY = new Date(2025, 1, 15);

function Harness({
  initial,
  onChange,
}: {
  initial: FilterValue;
  onChange?: (v: FilterValue) => void;
}) {
  const [value, setValue] = useState(initial);
  return (
    <FilterBar
      value={value}
      today={TODAY}
      onChange={(next) => {
        setValue(next);
        onChange?.(next);
      }}
    />
  );
}

describe("FilterBar (FR-5.4)", () => {
  it("applies a date preset and shows it as a removable chip", async () => {
    const user = userEvent.setup();
    const changes: FilterValue[] = [];
    render(
      <Harness initial={{ types: [], from: null, to: null }} onChange={(v) => changes.push(v)} />,
    );
    await user.click(screen.getByRole("button", { name: copy.filters.dateAny }));
    await user.click(await screen.findByRole("button", { name: copy.filters.presets.last30 }));
    expect(changes.at(-1)).toEqual({ types: [], from: "2025-01-16", to: "2025-02-15" });
    await user.keyboard("{Escape}");
    const chip = screen.getByRole("button", {
      name: copy.filters.remove(copy.filters.presets.last30),
    });
    await user.click(chip);
    expect(changes.at(-1)).toEqual({ types: [], from: null, to: null });
  });

  it("marks a non-preset range as Custom", async () => {
    const user = userEvent.setup();
    render(<Harness initial={{ types: [], from: "2024-03-01", to: "2024-04-01" }} />);
    await user.click(screen.getByRole("button", { name: /^Mar 1, 2024 to Apr 1, 2024/ }));
    const custom = await screen.findByRole("button", { name: copy.filters.presets.custom });
    expect(custom.className).toContain("bg-secondary");
  });

  it("clears every filter at once", async () => {
    const user = userEvent.setup();
    const changes: FilterValue[] = [];
    render(
      <Harness
        initial={{ types: ["Observation"], from: "2024-03-01", to: "2024-04-01" }}
        onChange={(v) => changes.push(v)}
      />,
    );
    const clear = screen.getAllByRole("button", { name: copy.filters.clear });
    await user.click(must(clear.at(-1)));
    expect(changes.at(-1)).toEqual({ types: [], from: null, to: null });
  });

  it("closes the mobile sheet with Show results (gap 13)", async () => {
    const user = userEvent.setup();
    render(<Harness initial={{ types: [], from: null, to: null }} />);
    await user.click(screen.getByRole("button", { name: copy.filters.mobileButton(0) }));
    await user.click(await screen.findByRole("button", { name: copy.filters.done }));
    await waitFor(() => {
      expect(screen.queryByRole("dialog")).toBeNull();
    });
  });

  it("has no serious axe violations", async () => {
    const { container } = render(
      <Harness initial={{ types: ["DiagnosticReport"], from: null, to: null }} />,
    );
    expect(await seriousAxeViolations(container)).toEqual([]);
  });
});
