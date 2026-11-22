import type { Meta, StoryObj } from "@storybook/react-vite";

import { SignInPhoto } from "@/features/auth/SignInPhoto";

const meta = {
  title: "Auth/SignInPhoto",
  component: SignInPhoto,
  decorators: [
    (Story) => (
      <div className="grid h-[32rem] max-w-3xl">
        <Story />
      </div>
    ),
  ],
} satisfies Meta<typeof SignInPhoto>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Photo: Story = {};
