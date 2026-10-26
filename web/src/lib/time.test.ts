import { describe, expect, it } from "vitest";
import { formatClock } from "./time";

describe("formatClock", () => {
  it("formats an ISO timestamp as a zero-padded local clock time", () => {
    const stamp = new Date(2026, 9, 26, 7, 5, 9).toISOString();
    expect(formatClock(stamp)).toBe("07:05:09");
  });

  it("returns an em dash for an unparseable timestamp", () => {
    expect(formatClock("not a date")).toBe("—");
  });
});
