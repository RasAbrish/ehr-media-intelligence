/** True while a modal surface (drawer sheet or dialog) is open; global shortcuts yield to it. */
export function modalOpen(kind: "any" | "dialog" = "any"): boolean {
  const selector =
    kind === "dialog"
      ? '[data-slot="dialog-content"]'
      : '[data-slot="sheet-content"], [data-slot="dialog-content"]';
  return document.querySelector(selector) !== null;
}
