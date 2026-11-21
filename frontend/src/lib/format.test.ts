import { ageSex, formatDate, formatDateLong, formatScore, percent } from "@/lib/format";

describe("format", () => {
  it("formats clinical dates as MMM D, YYYY without time zone drift", () => {
    expect(formatDate("2025-02-02")).toBe("Feb 2, 2025");
    expect(formatDate("2024-12-31")).toBe("Dec 31, 2024");
    expect(formatDateLong("2025-02-04")).toBe("February 4, 2025");
    expect(formatDate(null)).toBeNull();
    expect(formatDate("not a date")).toBeNull();
  });

  it("writes age and sex compactly with a long form", () => {
    expect(ageSex(57, "female")).toEqual({ short: "57 F", long: "57 years, female" });
    expect(ageSex(null, "male")).toEqual({ short: "M", long: "male" });
    expect(ageSex(40, "weird").short).toBe("40 U");
  });

  it("scores", () => {
    expect(percent(0.8123)).toBe(81);
    expect(percent(1.4)).toBe(100);
    expect(formatScore(0.8123)).toBe("0.81");
  });
});
