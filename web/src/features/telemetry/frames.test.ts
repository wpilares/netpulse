import { describe, expect, it } from "vitest";
import { makePort, makeSnapshot } from "./fixtures";
import { parseKpiSnapshot, parseLiveFrame } from "./frames";

describe("parseLiveFrame", () => {
  it("parses control frames", () => {
    expect(parseLiveFrame({ type: "hello", version: "0.3.0" })).toEqual({ type: "hello", version: "0.3.0" });
    expect(parseLiveFrame({ type: "pong" })).toEqual({ type: "pong" });
    expect(parseLiveFrame({ type: "error", reason: "bad request" })).toEqual({ type: "error", reason: "bad request" });
    expect(parseLiveFrame({ type: "heartbeat", at: "2026-10-26T10:00:00Z" })).toEqual({
      type: "heartbeat",
      at: "2026-10-26T10:00:00Z",
    });
    expect(parseLiveFrame({ type: "store_unavailable", at: "2026-10-26T10:00:00Z" })).toEqual({
      type: "store_unavailable",
      at: "2026-10-26T10:00:00Z",
    });
  });

  it("parses a kpis frame with its summary and switches", () => {
    const snapshot = makeSnapshot([makePort(), makePort({ port_no: 2, rx_bps: null, utilization: null })]);
    const frame = parseLiveFrame({ type: "kpis", ...snapshot });

    expect(frame).toEqual({ type: "kpis", ...snapshot });
  });

  it.each([
    null,
    "kpis",
    { type: "unknown" },
    { type: "hello" },
    { type: "heartbeat", at: 12 },
    { type: "kpis", generated_at: "2026-10-26T10:00:00Z", summary: {}, switches: [] },
    {
      type: "kpis",
      generated_at: "2026-10-26T10:00:00Z",
      summary: makeSnapshot([]).summary,
      switches: [{ dpid: 1, generated_at: "2026-10-26T10:00:00Z", ports: [{ dpid: 1 }] }],
    },
  ])("rejects malformed frame %j", (payload) => {
    expect(parseLiveFrame(payload)).toBeNull();
  });
});

describe("parseKpiSnapshot", () => {
  it("parses the REST summary payload", () => {
    const snapshot = makeSnapshot([makePort({ counter_reset: true })]);
    expect(parseKpiSnapshot(snapshot)).toEqual(snapshot);
  });

  it("rejects a port with a non-boolean counter reset flag", () => {
    const snapshot = makeSnapshot([makePort()]);
    const broken = {
      ...snapshot,
      switches: [{ ...snapshot.switches[0], ports: [{ ...makePort(), counter_reset: "yes" }] }],
    };
    expect(parseKpiSnapshot(broken)).toBeNull();
  });
});
