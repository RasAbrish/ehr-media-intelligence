import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { TooltipProvider } from "@/components/ui/tooltip";
import { ResultCard } from "@/features/search/ResultCard";
import type { SearchResult } from "@/features/search/schemas";
import { copy } from "@/lib/copy";
import { seriousAxeViolations } from "@/test/axe";
import { must } from "@/test/must";
import { fixtures } from "@/test/msw/fixtures";

const base = must(fixtures.search.results[0]);

function renderCard(result: SearchResult = base) {
  const onOpen = vi.fn();
  const view = render(
    <TooltipProvider>
      <ul>
        <li>
          <ResultCard result={result} onOpen={onOpen} />
        </li>
      </ul>
    </TooltipProvider>,
  );
  return { ...view, onOpen };
}

describe("ResultCard (FR-5.2)", () => {
  it("shows name and MRN, record date, type badge, score and the AI line", () => {
    renderCard();
    const card = screen.getByRole("article", { name: base.patient.display_name });
    expect(within(card).getByText(copy.card.mrn(base.patient.mrn))).toBeInTheDocument();
    const time = within(card).getByText("Feb 2, 2025");
    expect(time.tagName).toBe("TIME");
    expect(time).toHaveAttribute("dateTime", "2025-02-02");
    expect(within(card).getByText(copy.resourceLabels.DiagnosticReport)).toBeInTheDocument();
    expect(within(card).getByRole("img", { name: copy.card.relevance(81) })).toHaveTextContent(
      "0.81",
    );
    expect(within(card).getByText(copy.ai.badge)).toBeInTheDocument();
    expect(within(card).getByText(base.summary_snippet ?? "")).toBeInTheDocument();
  });

  it("marks matched terms with <mark> and never renders HTML from the snippet", () => {
    renderCard({ ...base, snippet: "<b>Potassium</b> 5.9", highlights: [[3, 12]] });
    expect(screen.getByText("Potassium").tagName).toBe("MARK");
    expect(document.querySelector("article b")).toBeNull();
  });

  it("opens the patient on click and on Enter", async () => {
    const user = userEvent.setup();
    const { onOpen } = renderCard();
    const button = screen.getByRole("button", {
      name: copy.card.open(base.patient.display_name, base.resource.title),
    });
    await user.click(button);
    button.focus();
    await user.keyboard("{Enter}");
    expect(onOpen).toHaveBeenCalledTimes(2);
  });

  it("opens from a click on the text, but not when the user selects text to copy", async () => {
    const user = userEvent.setup();
    const { onOpen } = renderCard();
    await user.click(screen.getByText(base.summary_snippet ?? ""));
    expect(onOpen).toHaveBeenCalledTimes(1);
    const selection = vi
      .spyOn(window, "getSelection")
      .mockReturnValue({ toString: () => "Potassium" } as Selection);
    await user.click(screen.getByText(base.summary_snippet ?? ""));
    expect(onOpen).toHaveBeenCalledTimes(1);
    selection.mockRestore();
  });

  it("describes the whole card to screen readers from its button", () => {
    renderCard();
    const button = screen.getByRole("button", {
      name: copy.card.open(base.patient.display_name, base.resource.title),
    });
    const description = (button.getAttribute("aria-describedby") ?? "")
      .split(" ")
      .map(
        (id) =>
          document.getElementById(id)?.textContent ??
          document.getElementById(id)?.getAttribute("aria-label"),
      )
      .join(" | ");
    expect(description).toContain("Feb 2, 2025");
    expect(description).toContain(base.resource.title);
    expect(description).toContain(base.summary_snippet ?? "");
    expect(description).toContain(base.snippet);
    const score = document.getElementById(`result-${base.rank}-score`);
    expect(score).toHaveAttribute("aria-label", copy.card.relevance(81));
  });

  it("flags identity conflicts and missing summaries", () => {
    renderCard({
      ...base,
      patient: { ...base.patient, identity_conflict: true },
      summary_snippet: null,
    });
    expect(screen.getByText(copy.card.conflict)).toBeInTheDocument();
    expect(screen.getByText(copy.card.noSummary)).toBeInTheDocument();
    expect(screen.queryByText(copy.ai.badge)).toBeNull(); // no AI marker on non-AI text
  });

  it("explains why the result matched", async () => {
    const user = userEvent.setup();
    renderCard();
    await user.click(screen.getByRole("button", { name: copy.why.trigger }));
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText(copy.why.matchTypes.hybrid)).toBeInTheDocument();
    expect(within(dialog).getByText("0.73")).toBeInTheDocument();
  });

  it("leaves no stray separator without a date (gap 10)", () => {
    renderCard({ ...base, resource: { ...base.resource, date: null } });
    const meta = must(document.getElementById(`result-${base.rank}-meta`));
    expect(meta.querySelector("time")).toBeNull();
    expect(meta.textContent).not.toContain("·");
  });

  it("shows the truncated title in a tooltip (gap 15)", async () => {
    const user = userEvent.setup();
    renderCard();
    const title = screen.getByText(base.resource.title);
    expect(title).not.toHaveAttribute("title");
    await user.hover(title);
    await waitFor(() => {
      expect(screen.getAllByText(base.resource.title)).toHaveLength(2);
    });
  });

  it("draws empty score segments with the muted token (gap 15)", () => {
    renderCard({ ...base, score: 0.4 });
    const meter = screen.getByRole("img", { name: copy.card.relevance(40) });
    expect(meter.querySelectorAll(".bg-muted")).toHaveLength(3);
  });

  it("sits one heading level below the page title", () => {
    renderCard();
    expect(
      screen.getByRole("heading", { level: 2, name: base.patient.display_name }),
    ).toBeVisible();
  });

  it("has no serious axe violations", async () => {
    const { container } = renderCard();
    expect(await seriousAxeViolations(container)).toEqual([]);
  });
});
