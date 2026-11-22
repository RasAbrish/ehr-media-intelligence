import { useMutation, useQuery } from "@tanstack/react-query";
import { ThumbsDownIcon, ThumbsUpIcon } from "lucide-react";
import { useId, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { Popover, PopoverContent, PopoverTitle, PopoverTrigger } from "@/components/ui/popover";
import { sendFeedback, type FeedbackVote } from "@/features/patients/api";
import type { ClinicalSummaryResponse } from "@/features/patients/schemas";
import { copy } from "@/lib/copy";
import { ApiError } from "@/lib/problem";
import { readStored, writeStored } from "@/lib/storage";
import { readyQuery } from "@/lib/system-api";

const COMMENT_MAX = 280;
type Rating = FeedbackVote["rating"];
type Reason = NonNullable<FeedbackVote["reason"]>;
const REASONS = Object.keys(copy.feedback.reasons) as Reason[];

function storedVote(key: string): Rating | null {
  const value = readStored(key);
  return value === "helpful" || value === "not_helpful" ? value : null;
}

/** Helpful / not helpful for one summary version (docs/06 section 12.2, FR-7.5). */
export function SummaryFeedback({ summary }: { summary: ClinicalSummaryResponse }) {
  const ready = useQuery(readyQuery());
  if (!ready.data?.flags.feedback_enabled) return null;
  return <FeedbackControls key={summary.cache_key} summary={summary} />;
}

function FeedbackControls({ summary }: { summary: ClinicalSummaryResponse }) {
  const ids = { group: useId(), comment: useId() };
  const storageKey = `mi-feedback:${summary.cache_key}`;
  const [vote, setVote] = useState(() => storedVote(storageKey));
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState<Reason | null>(null);
  const [comment, setComment] = useState("");
  const statusRef = useRef<HTMLParagraphElement>(null);

  const save = useMutation({
    mutationFn: (body: FeedbackVote) => sendFeedback(summary.patient_key, body),
    // Optimistic: the choice shows at once and rolls back if saving fails.
    onMutate: (body) => {
      setVote(body.rating);
      setOpen(false);
    },
    onSuccess: (_, body) => {
      writeStored(storageKey, body.rating);
      statusRef.current?.focus(); // the buttons are now static and cannot keep focus
    },
    onError: () => {
      setVote(null);
    },
  });

  const duplicate = save.error instanceof ApiError && save.error.status === 409;
  const locked = vote !== null || duplicate || save.isPending;
  let status = "";
  if (duplicate) status = copy.feedback.duplicate;
  else if (save.error instanceof ApiError && save.error.status === 429) {
    status = copy.errors.rateLimitedFinal(save.error.retryAfterSeconds ?? 60);
  } else if (save.isError) status = copy.feedback.failed;
  else if (save.isPending) status = copy.feedback.saving;
  else if (vote !== null) status = copy.feedback.thanks(summary.prompt_version);

  const send = (rating: Rating) => {
    save.mutate({
      cache_key: summary.cache_key,
      rating,
      reason: rating === "not_helpful" ? reason : null,
      comment: rating === "not_helpful" && comment.trim() ? comment.trim() : null,
    });
  };

  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-small text-muted-foreground">{copy.feedback.question}</span>
        <Button
          variant="outline"
          className="h-8 max-md:h-11"
          aria-pressed={vote === "helpful"}
          disabled={locked}
          onClick={() => {
            send("helpful");
          }}
        >
          <ThumbsUpIcon aria-hidden data-icon="inline-start" />
          {copy.feedback.helpful}
        </Button>
        <Popover open={open} onOpenChange={setOpen}>
          <PopoverTrigger
            render={
              <Button
                variant="outline"
                className="h-8 max-md:h-11"
                aria-pressed={vote === "not_helpful"}
                disabled={locked}
              />
            }
          >
            <ThumbsDownIcon aria-hidden data-icon="inline-start" />
            {copy.feedback.notHelpful}
          </PopoverTrigger>
          <PopoverContent align="end" className="w-80 p-3">
            <PopoverTitle className="text-heading">{copy.feedback.formTitle}</PopoverTitle>
            <form
              className="flex flex-col gap-3"
              onSubmit={(event) => {
                event.preventDefault();
                send("not_helpful");
              }}
            >
              <fieldset className="flex flex-col">
                <legend className="text-meta text-muted-foreground">{copy.feedback.reason}</legend>
                {REASONS.map((value) => (
                  <label
                    key={value}
                    className="flex min-h-8 items-center gap-2 text-body max-md:min-h-11"
                  >
                    <input
                      type="radio"
                      name={ids.group}
                      value={value}
                      checked={reason === value}
                      onChange={() => {
                        setReason(value);
                      }}
                      className="size-4 accent-primary"
                    />
                    {copy.feedback.reasons[value]}
                  </label>
                ))}
              </fieldset>
              <div className="flex flex-col gap-1">
                <label htmlFor={ids.comment} className="text-meta text-muted-foreground">
                  {copy.feedback.comment}
                </label>
                <textarea
                  id={ids.comment}
                  rows={3}
                  maxLength={COMMENT_MAX}
                  value={comment}
                  aria-describedby={`${ids.comment}-hint`}
                  onChange={(event) => {
                    setComment(event.target.value);
                  }}
                  className="rounded-lg border border-input bg-card p-2 text-small focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/25 focus-visible:outline-none"
                />
                <p
                  id={`${ids.comment}-hint`}
                  className="flex justify-between gap-2 text-meta text-muted-foreground"
                >
                  <span>{copy.feedback.privacy}</span>
                  <span className="tabular-nums">
                    {copy.feedback.counter(comment.length, COMMENT_MAX)}
                  </span>
                </p>
              </div>
              <Button type="submit" className="h-8 max-md:h-11" disabled={reason === null}>
                {copy.feedback.submit}
              </Button>
            </form>
          </PopoverContent>
        </Popover>
      </div>
      <p
        ref={statusRef}
        role="status"
        tabIndex={-1}
        className="text-meta text-muted-foreground outline-none"
      >
        {status}
      </p>
    </div>
  );
}
