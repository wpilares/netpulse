import type { ReactNode } from "react";
import { Badge, Button } from "../../components/ui";
import { formatClock, formatRelative } from "../../lib/time";
import styles from "./AlertRow.module.css";
import { type Alert, describeAlert, formatMetricValue, formatZscore } from "./alerts";

export interface AlertRowProps {
  readonly alert: Alert;
  readonly now: number;
  readonly pending?: boolean;
  readonly onAcknowledge?: (id: number) => void;
}

const AlertMark = ({ alert, now }: { readonly alert: Alert; readonly now: number }) => {
  if (alert.status === "resolved") {
    return <span className={styles.mark}>Resolved {formatRelative(alert.resolved_at ?? alert.updated_at, now)}</span>;
  }
  return <span className={styles.mark}>Acknowledged</span>;
};

const Stat = ({ label, children }: { readonly label: string; readonly children: ReactNode }) => (
  <div className={styles.stat}>
    <dt className={styles.statLabel}>{label}</dt>
    <dd className={styles.statValue}>{children}</dd>
  </div>
);

export const AlertRow = ({ alert, now, pending = false, onAcknowledge }: AlertRowProps) => {
  const acknowledged = alert.acknowledged_at !== null;
  const actionable = alert.status === "open" && !acknowledged && onAcknowledge !== undefined;
  return (
    <li
      className={styles.row}
      data-tone={alert.severity}
      data-severity={alert.severity}
      data-status={alert.status}
      data-acknowledged={acknowledged}
      aria-label={describeAlert(alert)}
    >
      <div className={styles.head}>
        <Badge tone={alert.severity} variant="solid">
          {alert.severity}
        </Badge>
        <span className={styles.target}>
          Switch {alert.dpid} · Port {alert.port_no}
        </span>
        <Badge tone="neutral" className={styles.metric}>
          {alert.metric}
        </Badge>
      </div>
      <dl className={styles.stats}>
        <Stat label="Value">{formatMetricValue(alert.metric, alert.value)}</Stat>
        <Stat label="Expected">{formatMetricValue(alert.metric, alert.expected)}</Stat>
        <Stat label="z-score">{formatZscore(alert.zscore)}</Stat>
        <Stat label="Opened">
          <time dateTime={alert.opened_at}>{formatClock(alert.opened_at)}</time>{" "}
          <span className={styles.ago}>{formatRelative(alert.opened_at, now)}</span>
        </Stat>
      </dl>
      <div className={styles.actions}>
        {actionable ? (
          <Button size="sm" loading={pending} onClick={() => onAcknowledge(alert.id)}>
            Acknowledge
          </Button>
        ) : (
          <AlertMark alert={alert} now={now} />
        )}
      </div>
    </li>
  );
};
