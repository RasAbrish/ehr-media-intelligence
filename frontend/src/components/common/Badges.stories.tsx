import type { Meta, StoryObj } from "@storybook/react-vite";

import { AiBadge } from "@/components/common/AiBadge";
import { ResourceTypeBadge } from "@/components/common/ResourceTypeBadge";
import { ScoreMeter } from "@/components/common/ScoreMeter";
import { SeverityBadge } from "@/components/common/SeverityBadge";

const meta: Meta = { title: "Common/Badges and meters" };
export default meta;

export const ResourceTypes: StoryObj = {
  render: () => (
    <div className="flex flex-wrap gap-2">
      {(
        [
          "DocumentReference",
          "DiagnosticReport",
          "Observation",
          "ClinicalSummary",
          "Encounter",
        ] as const
      ).map((type) => (
        <ResourceTypeBadge key={type} type={type} />
      ))}
    </div>
  ),
};

export const Severity: StoryObj = {
  render: () => (
    <div className="flex flex-wrap gap-2">
      <SeverityBadge severity="high" />
      <SeverityBadge severity="moderate" />
      <SeverityBadge severity="low" suffix="DQ" />
      <AiBadge />
    </div>
  ),
};

export const Scores: StoryObj = {
  render: () => (
    <div className="flex flex-col gap-2">
      {[0.12, 0.41, 0.66, 0.81, 1].map((score) => (
        <ScoreMeter key={score} score={score} />
      ))}
    </div>
  ),
};
