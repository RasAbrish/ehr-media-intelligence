/** True when a key press belongs to a field, so single-key shortcuts must not take it. */
export function isTypingTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  return target.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName);
}

/** Focus the page's own search field; false when the page has none. */
export function focusPageSearch(): boolean {
  const field = document.querySelector<HTMLInputElement>("[data-page-search]");
  field?.focus();
  return field !== null;
}
