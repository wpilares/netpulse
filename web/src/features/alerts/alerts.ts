import { isApiError } from "../../api/client";
import { type Alert, type AlertMetric, alertListSchema, alertSchema, parseWith } from "../../api/schemas";
import { formatBps, formatRate } from "../kpis/chart";

export type {
  Alert,
  AlertList,
  AlertMetric,
  AlertStatus,
  AlertStatusFilter,
  Severity,
} from "../../api/schemas";

export interface AlertSummary {
  readonly open: number;
  readonly critical: number;
  readonly warning: number;
  readonly acknowledged: number;
}

export const parseAlert = parseWith(alertSchema);

export const parseAlertList = parseWith(alertListSchema);

export const describeAlertError = (error: unknown): string => {
  if (isApiError(error)) {
    switch (error.kind) {
      case "not_found":
        return "Alert not found";
      case "unavailable":
        return "Alert storage unavailable";
      case "invalid":
        return "Alerts response could not be read";
      case "network":
        return "Alerts API unreachable";
    }
  }
  return "Alerts unavailable";
};

const byNewestOpened = (left: Alert, right: Alert): number =>
  Date.parse(right.opened_at) - Date.parse(left.opened_at) || right.id - left.id;

export const upsertAlerts = (current: readonly Alert[], incoming: readonly Alert[]): Alert[] => {
  const byId = new Map(current.map((alert) => [alert.id, alert] as const));
  for (const alert of incoming) {
    byId.set(alert.id, alert);
  }
  return [...byId.values()].sort(byNewestOpened);
};

export const openAlerts = (alerts: readonly Alert[]): Alert[] => alerts.filter((alert) => alert.status === "open");

export const alertSummary = (alerts: readonly Alert[]): AlertSummary => {
  const open = openAlerts(alerts);
  return {
    open: open.length,
    critical: open.filter((alert) => alert.severity === "critical").length,
    warning: open.filter((alert) => alert.severity === "warning").length,
    acknowledged: open.filter((alert) => alert.acknowledged_at !== null).length,
  };
};

export const formatMetricValue = (metric: AlertMetric, value: number): string =>
  metric === "rx_bps" || metric === "tx_bps" ? formatBps(value) : formatRate(value);

export const formatZscore = (zscore: number): string => zscore.toFixed(1);

export const describeAlert = (alert: Alert): string =>
  `Port ${alert.port_no} on switch ${alert.dpid}: ${alert.metric} ${formatMetricValue(alert.metric, alert.value)}, ` +
  `expected ${formatMetricValue(alert.metric, alert.expected)} (z ${formatZscore(alert.zscore)})`;
