/** Narrow a value that a test fixture guarantees, failing loudly if it is missing. */
export function must<T>(value: T | null | undefined, what = "value"): T {
  if (value === null || value === undefined) throw new Error(`Test setup: missing ${what}`);
  return value;
}
