import type { Tone } from "../../components/tone";
import type { NetworkSummary } from "../telemetry/frames";
import { formatBps, formatCount, formatRate } from "./chart";

export interface SummaryTile {
  readonly id: string;
  readonly label: string;
  readonly value: string;
  readonly tone: Tone;
}

const UTILIZATION_CRITICAL = 0.9;
const UTILIZATION_WARNING = 0.7;

export const utilizationTone = (utilization: number | null): Tone => {
  if (utilization === null) {
    return "neutral";
  }
  if (utilization > UTILIZATION_CRITICAL) {
    return "critical";
  }
  return utilization > UTILIZATION_WARNING ? "warning" : "neutral";
};

export const lossTone = (rate: number | null): Tone => (rate !== null && rate > 0 ? "warning" : "neutral");

export const summaryTiles = (summary: NetworkSummary): readonly SummaryTile[] => [
  { id: "rx", label: "Inbound throughput", value: formatBps(summary.rx_bps), tone: "neutral" },
  { id: "tx", label: "Outbound throughput", value: formatBps(summary.tx_bps), tone: "neutral" },
  {
    id: "utilization",
    label: "Max utilization",
    value: formatRate(summary.max_utilization),
    tone: utilizationTone(summary.max_utilization),
  },
  { id: "drops", label: "Drop rate", value: formatRate(summary.drop_rate), tone: lossTone(summary.drop_rate) },
  { id: "errors", label: "Error rate", value: formatRate(summary.error_rate), tone: lossTone(summary.error_rate) },
  { id: "switches", label: "Switches", value: formatCount(summary.switches), tone: "neutral" },
  { id: "ports", label: "Ports", value: formatCount(summary.ports), tone: "neutral" },
  { id: "resets", label: "Counter resets", value: formatCount(summary.counter_resets), tone: "neutral" },
];

export const SUMMARY_TILE_COUNT = 8;
