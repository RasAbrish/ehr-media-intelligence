import type { Meta, StoryObj } from "@storybook/react-vite";

import { DemoBanner } from "@/components/common/DemoBanner";

const meta = { title: "Common/DemoBanner", component: DemoBanner } satisfies Meta<
  typeof DemoBanner
>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Waking: Story = {};
