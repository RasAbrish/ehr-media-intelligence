import { QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { delay, http, HttpResponse } from "msw";

import { createQueryClient } from "@/app/queryClient";
import { TooltipProvider } from "@/components/ui/tooltip";
import { ConfidenceMeter } from "@/features/patients/ConfidenceMeter";
import { SummaryFeedback } from "@/features/patients/SummaryFeedback";
import { copy } from "@/lib/copy";
import { seriousAxeViolations } from "@/test/axe";
import { fixtures } from "@/test/msw/fixtures";
import { problemResponse } from "@/test/msw/handlers";
import { server } from "@/test/msw/server";

const { cache_key, patient_key, prompt_version } = fixtures.summary;

function renderFeedback() {
  return render(
    <QueryClientProvider client={createQueryClient()}>
      <TooltipProvider>
        <SummaryFeedback summary={fixtures.summary} />
      </TooltipProvider>
    </QueryClientProvider>,
  );
}

const helpful = () => screen.findByRole("button", { name: copy.feedback.helpful });
const notHelpful = () => screen.findByRole("button", { name: copy.feedback.notHelpful });

function capture() {
  const sent: { body: unknown; client: string | null; key: unknown }[] = [];
  server.use(
    http.post("*/api/patients/:key/summary/feedback", async ({ request, params }) => {
      sent.push({
        body: await request.json(),
        client: request.headers.get("X-Client-Id"),
        key: params.key,
      });
      return HttpResponse.json(fixtures.feedback, { status: 201 });
    }),
  );
  return sent;
}

describe("SummaryFeedback (FR-7.5)", () => {
  it("sends a helpful vote with an anonymous client id and thanks the user", async () => {
    const user = userEvent.setup();
    const sent = capture();
    renderFeedback();
    await user.click(await helpful());
    expect(await screen.findByText(copy.feedback.thanks(prompt_version))).toBeInTheDocument();
    expect(sent).toEqual([
      {
        key: patient_key,
        client: expect.stringMatching(/^[0-9a-f-]{36}$/) as string,
        body: { cache_key, rating: "helpful", reason: null, comment: null },
      },
    ]);
    expect(await helpful()).toBeDisabled();
  });

  it("requires a reason for not helpful and sends the comment", async () => {
    const user = userEvent.setup();
    const sent = capture();
    renderFeedback();
    await user.click(await notHelpful());
    const submit = await screen.findByRole("button", { name: copy.feedback.submit });
    expect(submit).toBeDisabled();
    await user.click(screen.getByRole("radio", { name: copy.feedback.reasons.too_long }));
    const comment = screen.getByRole("textbox", { name: copy.feedback.comment });
    expect(comment).toHaveAttribute("maxlength", "280");
    await user.type(comment, "Too wordy");
    expect(screen.getByText(copy.feedback.counter(9, 280))).toBeInTheDocument();
    await user.click(submit);
    expect(await screen.findByText(copy.feedback.thanks(prompt_version))).toBeInTheDocument();
    expect(sent[0]?.body).toEqual({
      cache_key,
      rating: "not_helpful",
      reason: "too_long",
      comment: "Too wordy",
    });
  });

  it("selects at once and rolls back when saving fails", async () => {
    const user = userEvent.setup();
    server.use(
      http.post("*/api/patients/:key/summary/feedback", async () => {
        await delay(150);
        return problemResponse(500, "internal_error");
      }),
    );
    renderFeedback();
    await user.click(await helpful());
    expect(await helpful()).toHaveAttribute("aria-pressed", "true");
    expect(await screen.findByText(copy.feedback.failed)).toBeInTheDocument();
    expect(await helpful()).toHaveAttribute("aria-pressed", "false");
    expect(await helpful()).toBeEnabled();
  });

  it("treats a duplicate as already rated", async () => {
    const user = userEvent.setup();
    server.use(
      http.post("*/api/patients/:key/summary/feedback", () =>
        problemResponse(409, "feedback_duplicate"),
      ),
    );
    renderFeedback();
    await user.click(await helpful());
    expect(await screen.findByText(copy.feedback.duplicate)).toBeInTheDocument();
    expect(await helpful()).toBeDisabled();
  });

  it("shows the existing vote for this summary version", async () => {
    window.localStorage.setItem(`mi-feedback:${cache_key}`, "not_helpful");
    renderFeedback();
    expect(await notHelpful()).toHaveAttribute("aria-pressed", "true");
    expect(await notHelpful()).toBeDisabled();
  });

  it("works when storage is blocked", async () => {
    const user = userEvent.setup();
    const get = vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    const set = vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    const sent = capture();
    renderFeedback();
    await user.click(await helpful());
    expect(await screen.findByText(copy.feedback.thanks(prompt_version))).toBeInTheDocument();
    expect(sent[0]?.client).toBeTruthy();
    get.mockRestore();
    set.mockRestore();
  });

  it("hides when the server has feedback turned off", async () => {
    let asked = false;
    server.use(
      http.get("*/api/ready", () => {
        asked = true;
        return HttpResponse.json({
          ...fixtures.ready,
          flags: { ...fixtures.ready.flags, feedback_enabled: false },
        });
      }),
    );
    renderFeedback();
    await vi.waitFor(() => {
      expect(asked).toBe(true);
    });
    expect(screen.queryByRole("button", { name: copy.feedback.helpful })).toBeNull();
  });

  it("has no serious axe violations with the reason form open", async () => {
    const user = userEvent.setup();
    renderFeedback();
    await user.click(await notHelpful());
    await screen.findByRole("radio", { name: copy.feedback.reasons.other });
    expect(await seriousAxeViolations(document.body)).toEqual([]);
  });
});

describe("Confidence popover", () => {
  it("lists the rationale and the guardrail notes in plain language", async () => {
    const user = userEvent.setup();
    render(
      <ConfidenceMeter
        confidence={fixtures.summary.confidence}
        notes={[
          "fallback_extractive (refusal)",
          "ungrounded_removed (2)",
          "unsupported_diagnosis (1)",
          "high_anomaly_restored (1)",
          "instruction_echo_removed",
          "field_limits_applied",
          "shortened_by_retry",
          "trimmed",
        ]}
      />,
    );
    await user.click(screen.getByRole("button", { name: copy.confidence.trigger }));
    const popover = await screen.findByRole("dialog");
    expect(popover).toHaveTextContent(fixtures.summary.confidence.rationale);
    for (const text of Object.values(copy.confidence.notes)) {
      expect(popover).toHaveTextContent(text);
    }
    expect(popover).not.toHaveTextContent("ungrounded_removed");
  });

  it("says when no check changed the summary", async () => {
    const user = userEvent.setup();
    render(<ConfidenceMeter confidence={fixtures.summary.confidence} notes={[]} />);
    await user.click(screen.getByRole("button", { name: copy.confidence.trigger }));
    expect(await screen.findByText(copy.confidence.noNotes)).toBeInTheDocument();
  });
});
