import type { Meta, StoryObj } from "@storybook/react-vite";
import { expect, userEvent, within } from "storybook/test";

import { AppToaster } from "@/components/common/AppToaster";
import { BrandMark } from "@/components/common/BrandMark";
import { CopyButton } from "@/components/common/CopyButton";
import { MobileNav } from "@/components/common/MobileNav";
import { OnboardingTip } from "@/components/common/OnboardingTip";
import { PageHeader } from "@/components/common/PageHeader";
import { PrimaryNav } from "@/components/common/PrimaryNav";
import { ShortcutsDialog } from "@/components/common/ShortcutsDialog";
import { StatsPill } from "@/components/common/StatsPill";
import { ThemeToggle } from "@/components/common/ThemeToggle";
import { TopBar } from "@/components/common/TopBar";
import { copy } from "@/lib/copy";

const meta: Meta = { title: "Common/Shell" };
export default meta;

export const FullTopBar: StoryObj = { render: () => <TopBar /> };
export const Navigation: StoryObj = {
  render: () => (
    <div className="flex h-14 items-center gap-4">
      <BrandMark />
      <PrimaryNav />
      <MobileNav />
    </div>
  ),
};
export const StatsAndTheme: StoryObj = {
  render: () => (
    <div className="flex items-center gap-2">
      <StatsPill />
      <ThemeToggle />
    </div>
  ),
};
export const Header: StoryObj = {
  render: () => <PageHeader title={copy.quality.title} description={copy.quality.body} />,
};
export const FirstRunTip: StoryObj = { render: () => <OnboardingTip /> };
export const CopyWithToast: StoryObj = {
  render: () => (
    <>
      <CopyButton value="00012345" label={copy.card.copyMrn} confirmation="Copied MRN 00012345" />
      <AppToaster />
    </>
  ),
};
export const Shortcuts: StoryObj = {
  render: () => <ShortcutsDialog />,
  play: async () => {
    await userEvent.keyboard("?");
    await expect(
      await within(document.body).findByRole("dialog", { name: copy.shortcuts.title }),
    ).toBeInTheDocument();
  },
};
