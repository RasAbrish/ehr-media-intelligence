/** Forgiving readers for URL search values: the router parses `12345` as a number. */
const PATIENT_KEY = /^[0-9a-f-]{8,64}$/i;

export function textParam(value: unknown, max = 500): string | undefined {
  const text = typeof value === "number" ? String(value) : value;
  return typeof text === "string" && text.trim() ? text.slice(0, max) : undefined;
}

export function positiveInt(value: unknown): number | undefined {
  const number = Number(value);
  return Number.isSafeInteger(number) && number > 0 ? number : undefined;
}

export function oneOf<T extends string>(value: unknown, allowed: readonly T[]): T | undefined {
  return allowed.find((option) => option === value);
}

export function patientParam(value: unknown): string | undefined {
  return typeof value === "string" && PATIENT_KEY.test(value) ? value : undefined;
}

export const PAGE_SIZES = [25, 50, 100] as const;

export function pageSizeParam(value: unknown): number | undefined {
  return PAGE_SIZES.find((size) => size === Number(value));
}
