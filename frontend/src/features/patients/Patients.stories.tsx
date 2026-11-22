import type { Meta, StoryObj } from "@storybook/react-vite";

import { ConfidenceMeter } from "@/features/patients/ConfidenceMeter";
import { DirectoryTable } from "@/features/patients/DirectoryTable";
import { SummaryFeedback } from "@/features/patients/SummaryFeedback";
import { KpiStrip } from "@/features/quality/KpiStrip";
import { IssueSeverity, SeverityFilter } from "@/features/quality/SeverityControls";
import { fixtures } from "@/test/msw/fixtures";

const meta: Meta = { title: "Patients/Directory, feedback and quality" };
export default meta;
const noop = () => undefined;

export const Directory: StoryObj = {
  render: () => (
    <DirectoryTable
      items={fixtures.directory.items}
      sort="last_activity"
      order="desc"
      onSort={noop}
      onOpen={noop}
    />
  ),
};
export const Feedback: StoryObj = {
  render: () => <SummaryFeedback summary={fixtures.summary} />,
};
export const Confidence: StoryObj = {
  render: () => (
    <ConfidenceMeter confidence={fixtures.summary.confidence} notes={["ungrounded_removed (2)"]} />
  ),
};
export const QualityTiles: StoryObj = {
  render: () => <KpiStrip overview={fixtures.overview} />,
};
export const IssueSeverities: StoryObj = {
  render: () => (
    <div className="flex items-center gap-2">
      <IssueSeverity severity="info" />
      <IssueSeverity severity="warning" />
      <IssueSeverity severity="error" />
      <SeverityFilter value={undefined} onChange={noop} />
    </div>
  ),
};
