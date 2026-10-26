import { describe, expect, it } from "vitest";
import { makePort } from "../telemetry/fixtures";
import { formatBps, formatPps, formatRate, linePath, niceMax, seriesOf } from "./chart";

const frame = { width: 100, height: 50, xDomain: [0, 10] as const, yDomain: [0, 100] as const };

describe("linePath", () => {
  it("maps points into the frame with y growing upwards", () => {
    expect(
      linePath(
        [
          { x: 0, y: 0 },
          { x: 10, y: 100 },
        ],
        frame,
      ),
    ).toBe("M0 50L100 0");
  });

  it("breaks the path on null gaps", () => {
    expect(
      linePath(
        [
          { x: 0, y: 50 },
          { x: 5, y: null },
          { x: 10, y: 50 },
        ],
        frame,
      ),
    ).toBe("M0 25M100 25");
  });

  it("returns an empty path for no points and survives a degenerate domain", () => {
    expect(linePath([], frame)).toBe("");
    expect(linePath([{ x: 3, y: 3 }], { ...frame, xDomain: [3, 3], yDomain: [0, 0] })).toBe("M0 50");
  });
});

describe("niceMax", () => {
  it("rounds up to 1, 2 or 5 times a power of ten", () => {
    expect(niceMax(7_300_000)).toBe(10_000_000);
    expect(niceMax(1200)).toBe(2000);
    expect(niceMax(4.2)).toBe(5);
    expect(niceMax(0)).toBe(1);
    expect(niceMax(-3)).toBe(1);
  });
});

describe("formatters", () => {
  it("formats throughput in bit units", () => {
    expect(formatBps(0)).toBe("0 b/s");
    expect(formatBps(999)).toBe("999 b/s");
    expect(formatBps(1500)).toBe("1.5 kb/s");
    expect(formatBps(2_500_000)).toBe("2.5 Mb/s");
    expect(formatBps(1.2e9)).toBe("1.2 Gb/s");
    expect(formatBps(null)).toBe("—");
  });

  it("formats ratios as percentages with one decimal", () => {
    expect(formatRate(0.0123)).toBe("1.2%");
    expect(formatRate(1)).toBe("100.0%");
    expect(formatRate(null)).toBe("—");
  });

  it("formats packet rates", () => {
    expect(formatPps(120)).toBe("120 pps");
    expect(formatPps(12_345)).toBe("12.3 kpps");
    expect(formatPps(null)).toBe("—");
  });
});

describe("seriesOf", () => {
  it("turns port history into timestamped points for one field", () => {
    const points = seriesOf(
      [
        makePort({ computed_at: "2026-10-26T10:00:00Z", tx_bps: 5 }),
        makePort({ computed_at: "2026-10-26T10:00:05Z", tx_bps: null }),
      ],
      "tx_bps",
    );
    expect(points).toEqual([
      { x: Date.parse("2026-10-26T10:00:00Z"), y: 5 },
      { x: Date.parse("2026-10-26T10:00:05Z"), y: null },
    ]);
  });
});
