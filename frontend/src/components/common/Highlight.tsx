import { Fragment } from "react";

/**
 * Wrap the given character ranges of `text` in <mark>. Ranges come from the API; the text
 * is rendered as React text nodes only, so no HTML from the data is ever injected.
 */
export function Highlight({
  text,
  ranges,
}: {
  text: string;
  ranges: readonly (readonly [number, number])[];
}) {
  const parts: { text: string; marked: boolean }[] = [];
  let cursor = 0;
  const ordered = [...ranges].sort((a, b) => a[0] - b[0]);
  for (const [rawStart, rawEnd] of ordered) {
    const start = Math.max(rawStart, cursor);
    const end = Math.min(rawEnd, text.length);
    if (start >= end) continue;
    if (start > cursor) parts.push({ text: text.slice(cursor, start), marked: false });
    parts.push({ text: text.slice(start, end), marked: true });
    cursor = end;
  }
  if (cursor < text.length) parts.push({ text: text.slice(cursor), marked: false });
  return (
    <>
      {parts.map((part, index) =>
        part.marked ? (
          <mark key={index} className="rounded-sm bg-primary/12 px-0.5 text-foreground">
            {part.text}
          </mark>
        ) : (
          <Fragment key={index}>{part.text}</Fragment>
        ),
      )}
    </>
  );
}

/** The distinct lower-case words the ranges cover ("why this result"). */
export function matchedTerms(
  text: string,
  ranges: readonly (readonly [number, number])[],
): string[] {
  const terms = ranges.map(([start, end]) => text.slice(start, end).toLowerCase());
  return [...new Set(terms)].filter(Boolean);
}
