import type { Meta, StoryObj } from "@storybook/react-vite";

import { DataTable, serverColumns } from "@/components/common/DataTable";
import { Highlight } from "@/components/common/Highlight";
import { Pagination } from "@/components/common/Pagination";
import { RangeCalendar } from "@/components/common/RangeCalendar";

const meta: Meta = { title: "Common/Data" };
export default meta;

interface Row {
  test: string;
  count: number;
}
const helper = serverColumns<Row>();
const columns = helper.columns([
  helper.accessor("test", { header: "Test", cell: ({ row }) => row.original.test }),
  helper.accessor("count", { header: "Results", cell: ({ row }) => row.original.count }),
]);
const rows = [
  { test: "Potassium", count: 14 },
  { test: "Creatinine", count: 9 },
];
const noop = () => undefined;

export const Table: StoryObj = {
  render: () => (
    <DataTable
      label="Lab tests"
      columns={columns}
      rows={rows}
      rowId={(row) => row.test}
      numeric={["count"]}
    />
  ),
};
export const SortableTable: StoryObj = {
  render: () => (
    <DataTable
      label="Lab tests"
      columns={columns}
      rows={rows}
      rowId={(row) => row.test}
      sorting={[{ id: "count", desc: true }]}
      onSortingChange={noop}
    />
  ),
};
export const Paging: StoryObj = {
  render: () => (
    <Pagination page={2} pageSize={25} total={60} totalPages={3} onPage={noop} onPageSize={noop} />
  ),
};
export const PagingOnePage: StoryObj = {
  render: () => <Pagination page={1} pageSize={25} total={6} totalPages={1} onPage={noop} />,
};
export const Highlighted: StoryObj = {
  render: () => (
    <p>
      <Highlight text="Potassium 5.9 mmol/L, repeat in 4 hours" ranges={[[0, 9]]} />
    </p>
  ),
};
export const Calendar: StoryObj = {
  render: () => (
    <RangeCalendar
      selected={{ from: new Date(2025, 1, 3), to: new Date(2025, 1, 14) }}
      defaultMonth={new Date(2025, 1, 1)}
      onSelect={noop}
    />
  ),
};
