import type { Meta, StoryObj } from "@storybook/react-vite";
import { expect, userEvent, within } from "storybook/test";

import { ResultList } from "@/features/search/ResultList";
import { fixtures } from "@/test/msw/fixtures";
import { must } from "@/test/must";

const meta: Meta<typeof ResultList> = {
  title: "Search/ResultList",
  component: ResultList,
  args: { results: fixtures.search.results, onOpen: () => undefined },
};
export default meta;

export const Keyboard: StoryObj<typeof ResultList> = {
  play: async ({ canvasElement }) => {
    const buttons = within(canvasElement).getAllByRole("button", { name: /^Open / });
    must(buttons[0]).focus();
    await userEvent.keyboard("{ArrowDown}");
    await expect(buttons[1]).toHaveFocus();
    await userEvent.keyboard("{Home}");
    await expect(buttons[0]).toHaveFocus();
  },
};
