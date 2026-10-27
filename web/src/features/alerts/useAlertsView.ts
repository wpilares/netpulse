import type { Alert } from "../../api/schemas";
import type { AlertSummary } from "./alerts";
import { useAcknowledgeAlert } from "./useAcknowledgeAlert";
import { type AlertsQueryOptions, type ResolvedAlerts, useAlertsQuery } from "./useAlertsQuery";

export type { ResolvedAlerts } from "./useAlertsQuery";

export interface AlertsView {
  readonly alerts: readonly Alert[];
  readonly summary: AlertSummary;
  readonly pending: ReadonlySet<number>;
  readonly error: string | null;
  readonly acknowledge: (id: number) => Promise<void>;
  readonly resolved: ResolvedAlerts;
  readonly toggleResolved: () => void;
}

export const useAlertsView = (options: AlertsQueryOptions): AlertsView => {
  const { alerts, summary, error, resolved, toggleResolved } = useAlertsQuery(options);
  const { acknowledge, pending, error: acknowledgeError } = useAcknowledgeAlert();
  return { alerts, summary, pending, error: acknowledgeError ?? error, acknowledge, resolved, toggleResolved };
};
