import { Badge, Card, CardHeader, CardTitle } from "../../components/ui";
import type { PortKpis } from "../telemetry/frames";
import { formatPps, formatRate } from "./chart";
import styles from "./PortCard.module.css";
import { PortChart } from "./PortChart";

export interface PortCardProps {
  readonly port: PortKpis;
  readonly points: readonly PortKpis[];
}

const Stat = ({ label, value }: { readonly label: string; readonly value: string }) => (
  <div className={styles.stat}>
    <dt className={styles.statLabel}>{label}</dt>
    <dd className={styles.statValue}>{value}</dd>
  </div>
);

export const PortCard = ({ port, points }: PortCardProps) => {
  const headingId = `port-${port.dpid}-${port.port_no}-heading`;
  return (
    <Card className={styles.card} aria-labelledby={headingId} data-reset={port.counter_reset}>
      <CardHeader actions={port.counter_reset ? <Badge tone="warning">Counter reset</Badge> : undefined}>
        <CardTitle level={3} id={headingId}>
          Port {port.port_no}
        </CardTitle>
      </CardHeader>
      <dl className={styles.stats}>
        <Stat label="Utilization" value={formatRate(port.utilization)} />
        <Stat label="Drops" value={formatRate(port.drop_rate)} />
        <Stat label="Errors" value={formatRate(port.error_rate)} />
        <Stat label="Packets" value={`${formatPps(port.rx_pps)} in · ${formatPps(port.tx_pps)} out`} />
      </dl>
      <PortChart portNo={port.port_no} points={points} />
    </Card>
  );
};
