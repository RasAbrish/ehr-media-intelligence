/** Display formats from docs/06 section 14.2. Clinical dates are absolute, never relative. */
import { format, isValid, parseISO } from "date-fns";

/** "2025-02-02" → "Feb 2, 2025". Date-only strings are read as local calendar dates. */
export function formatDate(iso: string | null | undefined): string | null {
  if (!iso) return null;
  const parsed = parseISO(iso);
  return isValid(parsed) ? format(parsed, "MMM d, yyyy") : null;
}

/** Long form for screen readers: "February 2, 2025". */
export function formatDateLong(iso: string | null | undefined): string | null {
  if (!iso) return null;
  const parsed = parseISO(iso);
  return isValid(parsed) ? format(parsed, "MMMM d, yyyy") : null;
}

/** "Feb 2, 2025 13:02" in the viewer's time zone (24 h). */
export function formatDateTime(iso: string): string {
  const parsed = parseISO(iso);
  return isValid(parsed) ? format(parsed, "MMM d, yyyy HH:mm") : iso;
}

const SEX: Record<string, { short: string; long: string }> = {
  female: { short: "F", long: "female" },
  male: { short: "M", long: "male" },
  other: { short: "X", long: "other" },
  unknown: { short: "U", long: "unknown sex" },
};

/** "57 F" plus the long form "57 years, female" for a tooltip or label. */
export function ageSex(age: number | null, gender: string): { short: string; long: string } {
  const sex = SEX[gender] ?? { short: "U", long: "unknown sex" };
  if (age === null) return { short: sex.short, long: sex.long };
  return { short: `${age} ${sex.short}`, long: `${age} years, ${sex.long}` };
}

export function percent(score: number): number {
  return Math.round(Math.min(Math.max(score, 0), 1) * 100);
}

/** Score as shown on cards: two decimals, tabular. */
export function formatScore(score: number): string {
  return score.toFixed(2);
}
