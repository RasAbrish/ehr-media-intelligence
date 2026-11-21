import type { Meta, StoryObj } from "@storybook/react-vite";

import type { ClinicalSummaryResponse, PatientResourceItem } from "@/features/patients/schemas";
import { SummaryPanel } from "@/features/patients/SummaryPanel";
import { fixtures } from "@/test/msw/fixtures";

const resources = new Map<string, PatientResourceItem>(
  fixtures.resources.items.map((item) => [item.resource_id, item]),
);
const base: ClinicalSummaryResponse = fixtures.summary;

const meta: Meta<typeof SummaryPanel> = {
  title: "Patients/SummaryPanel",
  component: SummaryPanel,
  args: { summary: base, resources, onEvidence: () => undefined },
  decorators: [
    (Story) => (
      <div className="max-w-[560px]">
        <Story />
      </div>
    ),
  ],
};
export default meta;
type Story = StoryObj<typeof SummaryPanel>;

export const Anthropic: Story = {};
export const Extractive: Story = {
  args: {
    summary: {
      ...base,
      provider: "extractive",
      model: null,
      confidence: { level: "low", score: 0.4, rationale: "Offline extractive summary." },
    },
  },
};
export const SuspectedDiagnosis: Story = {
  args: {
    summary: {
      ...base,
      key_diagnoses: [
        ...base.key_diagnoses,
        { name: "Pulmonary embolism", status: "suspected", evidence: [] },
      ],
      guardrail_notes: ["unsupported_diagnosis (1)"],
    },
  },
};
export const SparseRecord: Story = {
  args: {
    summary: {
      ...base,
      chief_concern: "Not documented",
      key_diagnoses: [],
      recent_media: [],
      flagged_anomalies: [],
      overview: "Not documented",
      confidence: { level: "low", score: 0.4, rationale: "Fewer than 2 records." },
    },
  },
};
export const FallbackNotice: Story = {
  args: {
    summary: {
      ...base,
      provider: "extractive",
      model: null,
      guardrail_notes: ["fallback_extractive (provider_error)"],
    },
  },
};
