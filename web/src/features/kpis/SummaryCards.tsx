import type { NetworkSummary } from "../telemetry/frames";
import { formatBps, formatCount, formatRate } from "./chart";

export interface SummaryCardsProps {
  readonly summary: NetworkSummary | null;
}

interface Card {
  readonly label: string;
  readonly value: string;
}

const describeSummary = (summary: NetworkSummary | null): readonly Card[] => [
  { label: "Inbound throughput", value: formatBps(summary?.rx_bps ?? null) },
  { label: "Outbound throughput", value: formatBps(summary?.tx_bps ?? null) },
  { label: "Max utilization", value: formatRate(summary?.max_utilization ?? null) },
  { label: "Drop rate", value: formatRate(summary?.drop_rate ?? null) },
  { label: "Error rate", value: formatRate(summary?.error_rate ?? null) },
  { label: "Switches", value: formatCount(summary?.switches ?? null) },
  { label: "Ports", value: formatCount(summary?.ports ?? null) },
  { label: "Counter resets", value: formatCount(summary?.counter_resets ?? null) },
];

export const SummaryCards = ({ summary }: SummaryCardsProps) => (
  <dl className="summary">
    {describeSummary(summary).map((card) => (
      <div key={card.label} className="summary__card">
        <dt className="summary__label">{card.label}</dt>
        <dd className="summary__value">{card.value}</dd>
      </div>
    ))}
  </dl>
);
