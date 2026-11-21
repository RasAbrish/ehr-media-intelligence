import type { Meta, StoryObj } from "@storybook/react-vite";

import { ResultCard } from "@/features/search/ResultCard";
import type { SearchResult } from "@/features/search/schemas";
import { fixtures } from "@/test/msw/fixtures";
import { must } from "@/test/must";

const base: SearchResult = must(fixtures.search.results[0]);

const meta: Meta<typeof ResultCard> = {
  title: "Search/ResultCard",
  component: ResultCard,
  args: { result: base, onOpen: () => undefined },
  decorators: [
    (Story) => (
      <ul className="max-w-[1120px]">
        <li>
          <Story />
        </li>
      </ul>
    ),
  ],
};
export default meta;
type Story = StoryObj<typeof ResultCard>;

export const Normal: Story = {};
export const Selected: Story = { args: { selected: true } };
export const IdentityConflict: Story = {
  args: { result: { ...base, patient: { ...base.patient, identity_conflict: true } } },
};
export const NoSummary: Story = { args: { result: { ...base, summary_snippet: null } } };
export const LongTitle: Story = {
  args: {
    result: {
      ...base,
      resource: {
        ...base.resource,
        title:
          "Comprehensive metabolic panel with reflex magnesium and phosphorus, repeat after dialysis",
      },
    },
  },
};
export const AiSummaryHit: Story = {
  args: {
    result: {
      ...base,
      match_type: "semantic",
      resource: {
        ...base.resource,
        resource_type: "ClinicalSummary",
        resource_id: `summary:${base.patient.patient_key}`,
        subtype: null,
        title: "AI clinical summary",
      },
    },
  },
};
