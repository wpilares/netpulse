import { BellOff } from "lucide-react";
import { EmptyState } from "../../components/ui";
import { AlertRow } from "./AlertRow";
import styles from "./AlertsList.module.css";
import type { Alert } from "./alerts";

export interface AlertsListProps {
  readonly label: string;
  readonly alerts: readonly Alert[];
  readonly now: number;
  readonly emptyTitle: string;
  readonly emptyDescription: string;
  readonly pending?: ReadonlySet<number>;
  readonly onAcknowledge?: (id: number) => void;
}

const noPending: ReadonlySet<number> = new Set();

export const AlertsList = ({
  label,
  alerts,
  now,
  emptyTitle,
  emptyDescription,
  pending = noPending,
  onAcknowledge,
}: AlertsListProps) => {
  if (alerts.length === 0) {
    return <EmptyState icon={BellOff} title={emptyTitle} description={emptyDescription} />;
  }
  return (
    <ul className={styles.list} aria-label={label}>
      {alerts.map((alert) => (
        <AlertRow
          key={alert.id}
          alert={alert}
          now={now}
          pending={pending.has(alert.id)}
          {...(onAcknowledge === undefined ? {} : { onAcknowledge })}
        />
      ))}
    </ul>
  );
};
