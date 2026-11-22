import type { Meta, StoryObj } from "@storybook/react-vite";
import { useState } from "react";
import { expect, userEvent, within } from "storybook/test";

import { FilterBar } from "@/features/search/FilterBar";
import type { FilterValue } from "@/features/search/filters";
import { copy } from "@/lib/copy";

function Controlled({ initial }: { initial: FilterValue }) {
  const [value, setValue] = useState(initial);
  return <FilterBar value={value} onChange={setValue} today={new Date(2025, 1, 15)} />;
}

const meta: Meta = { title: "Search/FilterBar" };
export default meta;

export const Empty: StoryObj = {
  render: () => <Controlled initial={{ types: [], from: null, to: null }} />,
};
export const Active: StoryObj = {
  render: () => (
    <Controlled
      initial={{ types: ["DiagnosticReport", "Observation"], from: "2024-08-15", to: "2025-02-15" }}
    />
  ),
};
export const Keyboard: StoryObj = {
  render: () => <Controlled initial={{ types: [], from: null, to: null }} />,
  play: async ({ canvasElement }) => {
    within(canvasElement)
      .getByRole("button", { name: /^Type: All/ })
      .focus();
    await userEvent.keyboard("{Enter}");
    const option = await within(document.body).findByRole("checkbox", {
      name: copy.resourceLabels.DiagnosticReport,
    });
    option.focus();
    await userEvent.keyboard(" ");
    await expect(option).toBeChecked();
  },
};

export const DatePopover: StoryObj = {
  render: () => <Controlled initial={{ types: [], from: null, to: null }} />,
  play: async ({ canvasElement }) => {
    within(canvasElement)
      .getByRole("button", { name: new RegExp(copy.filters.dateAny) })
      .focus();
    await userEvent.keyboard("{Enter}");
    await expect(
      await within(document.body).findByRole("dialog", { name: copy.filters.dateLabel }),
    ).toBeInTheDocument();
  },
};
