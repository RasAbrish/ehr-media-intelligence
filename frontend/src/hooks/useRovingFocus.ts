import { useCallback, useRef, useState, type KeyboardEvent } from "react";

/**
 * One tab stop for a list of items; ↑ ↓ Home End move focus (docs/06 section 8.4).
 * Items register with `itemProps(index)`; no positive tabindex is ever used.
 */
export function useRovingFocus(count: number) {
  const [active, setActive] = useState(0);
  const refs = useRef<(HTMLElement | null)[]>([]);
  const current = Math.min(active, Math.max(count - 1, 0));

  const focus = useCallback(
    (index: number) => {
      if (count === 0) return;
      const next = Math.min(Math.max(index, 0), count - 1);
      setActive(next);
      refs.current[next]?.focus();
    },
    [count],
  );

  const onKeyDown = useCallback(
    (event: KeyboardEvent) => {
      const keys: Record<string, number> = {
        ArrowDown: current + 1,
        ArrowUp: current - 1,
        Home: 0,
        End: count - 1,
      };
      const target = keys[event.key];
      if (target === undefined) return;
      event.preventDefault();
      focus(target);
    },
    [count, current, focus],
  );

  const itemProps = (index: number) => ({
    ref: (element: HTMLElement | null) => {
      refs.current[index] = element;
    },
    tabIndex: index === current ? 0 : -1,
    onFocus: () => {
      setActive(index);
    },
  });

  return { focus, onKeyDown, itemProps, active: current };
}
