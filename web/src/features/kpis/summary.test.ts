import { describe, expect, it } from "vitest";
import type { NetworkSummary } from "../telemetry/frames";
import { lossTone, summaryTiles, utilizationTone } from "./summary";

const summary: NetworkSummary = {
  ports: 12,
  switches: 3,
  rx_bps: 4_200_000,
  tx_bps: 900,
  drop_rate: 0.001,
  error_rate: 0,
  max_utilization: 0.42,
  counter_resets: 1,
};

describe("utilizationTone", () => {
  it("is critical above 90 %, warning above 70 % and neutral otherwise", () => {
    expect(utilizationTone(0.95)).toBe("critical");
    expect(utilizationTone(0.9)).toBe("warning");
    expect(utilizationTone(0.75)).toBe("warning");
    expect(utilizationTone(0.7)).toBe("neutral");
    expect(utilizationTone(null)).toBe("neutral");
  });
});

describe("lossTone", () => {
  it("warns on any drops or errors", () => {
    expect(lossTone(0.0001)).toBe("warning");
    expect(lossTone(0)).toBe("neutral");
    expect(lossTone(null)).toBe("neutral");
  });
});

describe("summaryTiles", () => {
  it("formats every KPI with its tone", () => {
    expect(summaryTiles(summary).map((tile) => [tile.label, tile.value, tile.tone])).toEqual([
      ["Inbound throughput", "4.2 Mb/s", "neutral"],
      ["Outbound throughput", "900 b/s", "neutral"],
      ["Max utilization", "42.0%", "neutral"],
      ["Drop rate", "0.1%", "warning"],
      ["Error rate", "0.0%", "neutral"],
      ["Switches", "3", "neutral"],
      ["Ports", "12", "neutral"],
      ["Counter resets", "1", "neutral"],
    ]);
  });

  it("shows an em dash for missing values", () => {
    const empty: NetworkSummary = {
      ...summary,
      rx_bps: null,
      tx_bps: null,
      drop_rate: null,
      error_rate: null,
      max_utilization: null,
    };

    expect(summaryTiles(empty).filter((tile) => tile.value === "—")).toHaveLength(5);
  });
});
