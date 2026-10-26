import { isArrayOf, isNullableNumber, isRecord } from "../../lib/guards";

export interface PortKpis {
  readonly dpid: number;
  readonly port_no: number;
  readonly computed_at: string;
  readonly interval_seconds: number;
  readonly rx_bps: number | null;
  readonly tx_bps: number | null;
  readonly rx_pps: number | null;
  readonly tx_pps: number | null;
  readonly drop_rate: number | null;
  readonly error_rate: number | null;
  readonly utilization: number | null;
  readonly counter_reset: boolean;
}

export interface SwitchKpis {
  readonly dpid: number;
  readonly generated_at: string;
  readonly ports: readonly PortKpis[];
}

export interface NetworkSummary {
  readonly ports: number;
  readonly switches: number;
  readonly rx_bps: number | null;
  readonly tx_bps: number | null;
  readonly drop_rate: number | null;
  readonly error_rate: number | null;
  readonly max_utilization: number | null;
  readonly counter_resets: number;
}

export interface KpiSnapshot {
  readonly generated_at: string;
  readonly summary: NetworkSummary;
  readonly switches: readonly SwitchKpis[];
}

export interface KpiFrame extends KpiSnapshot {
  readonly type: "kpis";
}

export type LiveFrame =
  | { readonly type: "hello"; readonly version: string }
  | { readonly type: "pong" }
  | { readonly type: "error"; readonly reason: string }
  | { readonly type: "heartbeat"; readonly at: string }
  | { readonly type: "store_unavailable"; readonly at: string }
  | KpiFrame;

const parsePortKpis = (value: unknown): PortKpis | null => {
  if (!isRecord(value)) {
    return null;
  }
  const {
    dpid,
    port_no,
    computed_at,
    interval_seconds,
    rx_bps,
    tx_bps,
    rx_pps,
    tx_pps,
    drop_rate,
    error_rate,
    utilization,
    counter_reset,
  } = value;
  if (
    typeof dpid !== "number" ||
    typeof port_no !== "number" ||
    typeof computed_at !== "string" ||
    typeof interval_seconds !== "number" ||
    !isNullableNumber(rx_bps) ||
    !isNullableNumber(tx_bps) ||
    !isNullableNumber(rx_pps) ||
    !isNullableNumber(tx_pps) ||
    !isNullableNumber(drop_rate) ||
    !isNullableNumber(error_rate) ||
    !isNullableNumber(utilization) ||
    typeof counter_reset !== "boolean"
  ) {
    return null;
  }
  return {
    dpid,
    port_no,
    computed_at,
    interval_seconds,
    rx_bps,
    tx_bps,
    rx_pps,
    tx_pps,
    drop_rate,
    error_rate,
    utilization,
    counter_reset,
  };
};

const isPortKpis = (value: unknown): value is PortKpis => parsePortKpis(value) !== null;

const parseSwitchKpis = (value: unknown): SwitchKpis | null => {
  if (!isRecord(value)) {
    return null;
  }
  const { dpid, generated_at, ports } = value;
  if (typeof dpid !== "number" || typeof generated_at !== "string" || !isArrayOf(ports, isPortKpis)) {
    return null;
  }
  return { dpid, generated_at, ports };
};

const isSwitchKpis = (value: unknown): value is SwitchKpis => parseSwitchKpis(value) !== null;

const parseSummary = (value: unknown): NetworkSummary | null => {
  if (!isRecord(value)) {
    return null;
  }
  const { ports, switches, rx_bps, tx_bps, drop_rate, error_rate, max_utilization, counter_resets } = value;
  if (
    typeof ports !== "number" ||
    typeof switches !== "number" ||
    !isNullableNumber(rx_bps) ||
    !isNullableNumber(tx_bps) ||
    !isNullableNumber(drop_rate) ||
    !isNullableNumber(error_rate) ||
    !isNullableNumber(max_utilization) ||
    typeof counter_resets !== "number"
  ) {
    return null;
  }
  return { ports, switches, rx_bps, tx_bps, drop_rate, error_rate, max_utilization, counter_resets };
};

export const parseKpiSnapshot = (value: unknown): KpiSnapshot | null => {
  if (!isRecord(value)) {
    return null;
  }
  const { generated_at, switches } = value;
  const summary = parseSummary(value.summary);
  if (typeof generated_at !== "string" || summary === null || !isArrayOf(switches, isSwitchKpis)) {
    return null;
  }
  return { generated_at, summary, switches };
};

export const parseLiveFrame = (value: unknown): LiveFrame | null => {
  if (!isRecord(value) || typeof value.type !== "string") {
    return null;
  }
  switch (value.type) {
    case "hello":
      return typeof value.version === "string" ? { type: "hello", version: value.version } : null;
    case "pong":
      return { type: "pong" };
    case "error":
      return typeof value.reason === "string" ? { type: "error", reason: value.reason } : null;
    case "heartbeat":
      return typeof value.at === "string" ? { type: "heartbeat", at: value.at } : null;
    case "store_unavailable":
      return typeof value.at === "string" ? { type: "store_unavailable", at: value.at } : null;
    case "kpis": {
      const snapshot = parseKpiSnapshot(value);
      return snapshot === null ? null : { type: "kpis", ...snapshot };
    }
    default:
      return null;
  }
};
