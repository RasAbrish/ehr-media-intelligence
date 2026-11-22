import type { Meta, StoryObj } from "@storybook/react-vite";

import { SortSelect } from "@/features/search/SortSelect";

const meta = {
  title: "Search/SortSelect",
  component: SortSelect,
  args: { value: "relevance", onChange: () => undefined },
} satisfies Meta<typeof SortSelect>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Relevance: Story = {};
export const Newest: Story = { args: { value: "newest" } };
