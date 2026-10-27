import { describe, expect, it } from "vitest";
import { makeAlert, makeAlertsFrame } from "../features/alerts/fixtures";
import { makeKpiFrame, makePort, makeSnapshot } from "../features/telemetry/fixtures";
import { makeTopology } from "../features/topology/fixtures";
import {
  alertListSchema,
  alertSchema,
  healthReportSchema,
  kpiSnapshotSchema,
  liveFrameSchema,
  parseWith,
  topologySchema,
} from "./schemas";

describe("healthReportSchema", () => {
  it("accepts ok and degraded reports", () => {
    expect(healthReportSchema.safeParse({ status: "ok", database: "up", version: "1.0.0" }).success).toBe(true);
    expect(healthReportSchema.safeParse({ status: "degraded", database: "down", version: "1.0.0" }).success).toBe(true);
  });

  it("rejects unknown statuses and missing fields", () => {
    expect(healthReportSchema.safeParse({ status: "unknown", database: "up", version: "1.0.0" }).success).toBe(false);
    expect(healthReportSchema.safeParse({ status: "ok", database: "up" }).success).toBe(false);
  });
});

describe("kpiSnapshotSchema", () => {
  it("accepts a snapshot with nullable metrics and drops unknown keys", () => {
    const snapshot = makeSnapshot([makePort(), makePort({ port_no: 2, rx_bps: null, utilization: null })]);
    expect(kpiSnapshotSchema.parse({ ...snapshot, extra: true })).toEqual(snapshot);
  });

  it("rejects a port with a non-boolean counter reset flag", () => {
    const snapshot = makeSnapshot([makePort()]);
    const broken = {
      ...snapshot,
      switches: [{ ...snapshot.switches[0], ports: [{ ...makePort(), counter_reset: "yes" }] }],
    };
    expect(kpiSnapshotSchema.safeParse(broken).success).toBe(false);
  });
});

describe("topologySchema", () => {
  it("accepts the API payload", () => {
    const topology = makeTopology();
    expect(topologySchema.parse(topology)).toEqual(topology);
  });

  it.each([
    null,
    { nodes: [] },
    { ...makeTopology(), nodes: [{ id: "x" }] },
    { ...makeTopology(), edges: [{ source: 1 }] },
    { ...makeTopology(), nodes: [{ id: "s:1", kind: "router", dpid: 1, port_no: null, label: "s1" }] },
  ])("rejects malformed payload %j", (payload) => {
    expect(topologySchema.safeParse(payload).success).toBe(false);
  });
});

describe("alertSchema and alertListSchema", () => {
  it("accepts a full alert and its list envelope", () => {
    const alert = makeAlert({ acknowledged_at: "2026-10-26T10:01:00Z", resolved_at: "2026-10-26T10:02:00Z" });
    expect(alertSchema.parse(alert)).toEqual(alert);
    const list = { generated_at: "2026-10-26T10:00:05Z", alerts: [alert, makeAlert({ id: 2 })] };
    expect(alertListSchema.parse(list)).toEqual(list);
  });

  it.each([
    { ...makeAlert(), metric: "latency" },
    { ...makeAlert(), severity: "info" },
    { ...makeAlert(), status: "closed" },
    { ...makeAlert(), resolved_at: 12 },
    { ...makeAlert(), value: "9" },
    { ...makeAlert(), id: "1" },
    { ...makeAlert(), updated_at: undefined },
  ])("rejects malformed alert %j", (payload) => {
    expect(alertSchema.safeParse(payload).success).toBe(false);
  });

  it("rejects a list with a malformed alert or without a timestamp", () => {
    expect(alertListSchema.safeParse({ generated_at: "2026-10-26T10:00:05Z", alerts: [{ id: 1 }] }).success).toBe(
      false,
    );
    expect(alertListSchema.safeParse({ alerts: [] }).success).toBe(false);
  });
});

describe("liveFrameSchema", () => {
  it("discriminates control frames by type", () => {
    expect(liveFrameSchema.parse({ type: "hello", version: "1.0.0" })).toEqual({ type: "hello", version: "1.0.0" });
    expect(liveFrameSchema.parse({ type: "pong" })).toEqual({ type: "pong" });
    expect(liveFrameSchema.parse({ type: "error", reason: "bad request" })).toEqual({
      type: "error",
      reason: "bad request",
    });
    expect(liveFrameSchema.parse({ type: "heartbeat", at: "2026-10-26T10:00:00Z" })).toEqual({
      type: "heartbeat",
      at: "2026-10-26T10:00:00Z",
    });
    expect(liveFrameSchema.parse({ type: "store_unavailable", at: "2026-10-26T10:00:00Z" })).toEqual({
      type: "store_unavailable",
      at: "2026-10-26T10:00:00Z",
    });
  });

  it("parses kpis and alerts frames with their payloads", () => {
    const kpis = makeKpiFrame([makePort()]);
    expect(liveFrameSchema.parse(kpis)).toEqual(kpis);
    const alerts = makeAlertsFrame([makeAlert(), makeAlert({ id: 2, severity: "critical" })]);
    expect(liveFrameSchema.parse(alerts)).toEqual(alerts);
  });

  it.each([
    null,
    "kpis",
    { type: "unknown" },
    { type: "hello" },
    { type: "heartbeat", at: 12 },
    { type: "alerts", alerts: [] },
    { type: "kpis", generated_at: "2026-10-26T10:00:00Z", summary: {}, switches: [] },
  ])("rejects malformed frame %j", (payload) => {
    expect(liveFrameSchema.safeParse(payload).success).toBe(false);
  });
});

describe("parseWith", () => {
  it("returns the parsed value or null instead of throwing", () => {
    const parse = parseWith(healthReportSchema);
    expect(parse({ status: "ok", database: "disabled", version: "1.0.0" })).toEqual({
      status: "ok",
      database: "disabled",
      version: "1.0.0",
    });
    expect(parse("ok")).toBeNull();
    expect(parse(undefined)).toBeNull();
  });
});
