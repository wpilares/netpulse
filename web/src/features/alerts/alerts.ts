import {
  type Alert,
  type AlertList,
  type AlertMetric,
  type AlertStatusFilter,
  alertListSchema,
  alertSchema,
  parseWith,
} from "../../api/schemas";
import { formatBps, formatRate } from "../kpis/chart";

export type {
  Alert,
  AlertList,
  AlertMetric,
  AlertStatus,
  AlertStatusFilter,
  Severity,
} from "../../api/schemas";

const ALERTS_PATH = "/api/v1/alerts";

export interface AlertSummary {
  readonly open: number;
  readonly critical: number;
  readonly warning: number;
  readonly acknowledged: number;
}

export type AlertErrorKind = "not_found" | "unavailable" | "invalid";

export class AlertRequestError extends Error {
  constructor(
    readonly kind: AlertErrorKind,
    message: string,
  ) {
    super(message);
    this.name = "AlertRequestError";
  }
}

export interface FetchAlertsOptions {
  readonly status: AlertStatusFilter;
  readonly limit: number;
  readonly signal?: AbortSignal;
}

export const parseAlert = parseWith(alertSchema);

export const parseAlertList = parseWith(alertListSchema);

const failureFor = (status: number): AlertRequestError => {
  if (status === 404) {
    return new AlertRequestError("not_found", "alert not found");
  }
  if (status === 503) {
    return new AlertRequestError("unavailable", "alert storage unavailable");
  }
  return new AlertRequestError("unavailable", `alerts request failed with status ${status}`);
};

const request = async (fetcher: typeof fetch, input: string, init: RequestInit): Promise<Response> => {
  let response: Response;
  try {
    response = await fetcher(input, init);
  } catch {
    throw new AlertRequestError("unavailable", "alerts API unreachable");
  }
  if (!response.ok) {
    throw failureFor(response.status);
  }
  return response;
};

const parseBody = async <T>(response: Response, parse: (value: unknown) => T | null): Promise<T> => {
  let body: unknown;
  try {
    body = await response.json();
  } catch {
    throw new AlertRequestError("invalid", "alerts response is not JSON");
  }
  const parsed = parse(body);
  if (parsed === null) {
    throw new AlertRequestError("invalid", "alerts response has an unexpected shape");
  }
  return parsed;
};

export const fetchAlerts = async (
  fetcher: typeof fetch,
  { status, limit, signal }: FetchAlertsOptions,
): Promise<AlertList> => {
  const query = new URLSearchParams({ status, limit: String(limit) });
  const response = await request(fetcher, `${ALERTS_PATH}?${query}`, {
    headers: { Accept: "application/json" },
    ...(signal === undefined ? {} : { signal }),
  });
  return parseBody(response, parseAlertList);
};

export const acknowledgeAlert = async (fetcher: typeof fetch, id: number): Promise<Alert> => {
  const response = await request(fetcher, `${ALERTS_PATH}/${id}/ack`, {
    method: "POST",
    headers: { Accept: "application/json" },
  });
  return parseBody(response, parseAlert);
};

export const describeAlertError = (error: unknown): string => {
  if (error instanceof AlertRequestError) {
    switch (error.kind) {
      case "not_found":
        return "Alert not found";
      case "unavailable":
        return "Alert storage unavailable";
      case "invalid":
        return "Alerts response could not be read";
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
