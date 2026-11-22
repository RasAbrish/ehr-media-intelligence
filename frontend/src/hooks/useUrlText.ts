import { useCallback, useEffect, useRef, useState } from "react";

const DEBOUNCE_MS = 300;

/**
 * A text field mirrored into the URL after 300 ms without typing. URL changes from outside
 * (back button, link) update the field; adjusting state during render is React's pattern
 * for this, and our own pushes are skipped so typing is never overwritten.
 */
export function useUrlText(urlValue: string, write: (value: string, replace: boolean) => void) {
  const [draft, setDraft] = useState(urlValue);
  const [seen, setSeen] = useState(urlValue);
  const [pushed, setPushed] = useState(urlValue);
  const timer = useRef<number | undefined>(undefined);

  if (urlValue !== seen) {
    setSeen(urlValue);
    if (urlValue !== pushed) {
      setDraft(urlValue);
      setPushed(urlValue); // so a later return to an older pushed value also updates the field
    }
  }

  useEffect(
    () => () => {
      window.clearTimeout(timer.current);
    },
    [],
  );

  const push = useCallback(
    (value: string, replace: boolean) => {
      setPushed(value.trim());
      write(value.trim(), replace);
    },
    [write],
  );

  /** Typing: replace, so it does not fill the history. */
  const change = (value: string) => {
    setDraft(value);
    window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => {
      push(value, true);
    }, DEBOUNCE_MS);
  };

  /** A chosen value (example chip): applied at once, with a history entry. */
  const choose = (value: string) => {
    window.clearTimeout(timer.current);
    setDraft(value);
    push(value, false);
  };

  return { draft, change, choose };
}
