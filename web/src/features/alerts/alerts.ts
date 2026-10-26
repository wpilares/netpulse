import { isArrayOf, isOneOf, isRecord } from "../../lib/guards";
import { formatBps, formatRate } from "../kpis/chart";

const ALERTS_PATH = "/api/v1/alerts";
const ALERT_METRICS = ["rx_bps", "tx_bps", "drop_rate", "error_rate"] as const;
const SEVERITIES = ["warning", "critical"] as const;
const ALERT_STATUSES = ["open", "resolved"] as const;

export type AlertMetric = (typeof ALERT_METRICS)[number];
export type Severity = (typeof SEVERITIES)[number];
export type AlertStatus = (typeof ALERT_STATUSES)[number];
export type AlertStatusFilter = AlertStatus | "all";

export interface Alert {
  readonly id: number;
  readonly dpid: number;
  readonly port_no: number;
  readonly metric: AlertMetric;
  readonly severity: Severity;
  readonly status: AlertStatus;
  readonly opened_at: string;
  readonly last_seen_at: string;
  readonly resolved_at: string | null;
  readonly acknowledged_at: string | null;
  readonly value: number;
  readonly expected: number;
  readonly zscore: number;
  readonly updated_at: string;
}

export interface AlertList {
  readonly generated_at: string;
  readonly alerts: readonly Alert[];
}

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

const isNullableString = (value: unknown): value is string | null => value === null || typeof value === "string";

export const parseAlert = (value: unknown): Alert | null => {
  if (!isRecord(value)) {
    return null;
  }
  const {
    id,
    dpid,
    port_no,
    metric,
    severity,
    status,
    opened_at,
    last_seen_at,
    resolved_at,
    acknowledged_at,
    value: observed,
    expected,
    zscore,
    updated_at,
  } = value;
  if (
    typeof id !== "number" ||
    typeof dpid !== "number" ||
    typeof port_no !== "number" ||
    !isOneOf(ALERT_METRICS, metric) ||
    !isOneOf(SEVERITIES, severity) ||
    !isOneOf(ALERT_STATUSES, status) ||
    typeof opened_at !== "string" ||
    typeof last_seen_at !== "string" ||
    !isNullableString(resolved_at) ||
    !isNullableString(acknowledged_at) ||
    typeof observed !== "number" ||
    typeof expected !== "number" ||
    typeof zscore !== "number" ||
    typeof updated_at !== "string"
  ) {
    return null;
  }
  return {
    id,
    dpid,
    port_no,
    metric,
    severity,
    status,
    opened_at,
    last_seen_at,
    resolved_at,
    acknowledged_at,
    value: observed,
    expected,
    zscore,
    updated_at,
  };
};

const isAlert = (value: unknown): value is Alert => parseAlert(value) !== null;

export const parseAlertList = (value: unknown): AlertList | null => {
  if (!isRecord(value)) {
    return null;
  }
  const { generated_at, alerts } = value;
  if (typeof generated_at !== "string" || !isArrayOf(alerts, isAlert)) {
    return null;
  }
  return { generated_at, alerts };
};

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
