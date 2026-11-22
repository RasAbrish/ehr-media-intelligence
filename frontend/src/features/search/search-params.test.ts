import { DateRangeSchema, parseSearchParams } from "@/features/search/search-params";

describe("search URL params", () => {
  it("keeps valid values", () => {
    expect(
      parseSearchParams({
        q: "chest",
        type: ["DiagnosticReport", "Observation"],
        from: "2024-06-01",
        to: "2024-12-31",
        patient: "3b7f9c2e-5a41-5d0e-9b8a-1f2c3d4e5f60",
      }),
    ).toEqual({
      q: "chest",
      type: ["DiagnosticReport", "Observation"],
      from: "2024-06-01",
      to: "2024-12-31",
      patient: "3b7f9c2e-5a41-5d0e-9b8a-1f2c3d4e5f60",
    });
  });

  it("drops invalid values instead of failing", () => {
    expect(
      parseSearchParams({
        q: "  ",
        type: ["Patient", "DocumentReference", "DocumentReference"],
        from: "2024-02-30",
        to: "06/01/2024",
        patient: "<script>",
      }),
    ).toEqual({ type: ["DocumentReference"] });
    expect(parseSearchParams({ type: "ClinicalSummary" })).toEqual({ type: ["ClinicalSummary"] });
  });

  it("keeps only the start of an inverted range", () => {
    expect(parseSearchParams({ from: "2024-06-02", to: "2024-06-01" })).toEqual({
      from: "2024-06-02",
    });
  });

  it("keeps a numeric query from a hand-typed MRN link", () => {
    expect(parseSearchParams({ q: 12345 })).toEqual({ q: "12345" });
  });

  it("blocks an end date before the start date", () => {
    expect(DateRangeSchema.safeParse({ from: "2024-06-02", to: "2024-06-01" }).success).toBe(false);
    expect(DateRangeSchema.safeParse({ from: "2024-06-01", to: "2024-06-01" }).success).toBe(true);
    expect(DateRangeSchema.safeParse({ from: null, to: "2024-06-01" }).success).toBe(true);
  });
});
