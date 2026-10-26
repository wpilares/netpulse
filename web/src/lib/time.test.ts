import { describe, expect, it } from "vitest";
import { formatClock, formatRelative } from "./time";

describe("formatClock", () => {
  it("formats an ISO timestamp as a zero-padded local clock time", () => {
    const stamp = new Date(2026, 9, 26, 7, 5, 9).toISOString();
    expect(formatClock(stamp)).toBe("07:05:09");
  });

  it("returns an em dash for an unparseable timestamp", () => {
    expect(formatClock("not a date")).toBe("—");
  });
});

describe("formatRelative", () => {
  const now = Date.UTC(2026, 9, 26, 10, 10, 0);
  const secondsAgo = (ms: number): string => new Date(now - ms).toISOString();

  it.each([
    [0, "just now"],
    [4_000, "just now"],
    [5_000, "5 s ago"],
    [59_000, "59 s ago"],
    [60_000, "1 min ago"],
    [3_599_000, "59 min ago"],
    [3_600_000, "1 h ago"],
    [86_399_000, "23 h ago"],
    [86_400_000, "1 d ago"],
    [259_200_000, "3 d ago"],
  ])("describes %i ms ago as %s", (ms, expected) => {
    expect(formatRelative(secondsAgo(ms), now)).toBe(expected);
  });

  it("treats a future timestamp as just now", () => {
    expect(formatRelative(secondsAgo(-30_000), now)).toBe("just now");
  });

  it("returns an em dash for an unparseable timestamp", () => {
    expect(formatRelative("not a date", now)).toBe("—");
  });
});
