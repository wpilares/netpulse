import { formatClock, formatRelative } from "../../lib/time";
import { type Alert, describeAlert, formatMetricValue, formatZscore, type Severity } from "./alerts";
import type { AlertsView } from "./useAlertsView";

export interface AlertsPanelProps extends AlertsView {
  readonly now?: number;
}

interface AlertRowProps {
  readonly alert: Alert;
  readonly now: number;
  readonly pending: boolean;
  readonly onAcknowledge: ((id: number) => void) | null;
}

const SeverityBadge = ({ severity }: { readonly severity: Severity }) => (
  <span className="severity" data-tone={severity}>
    {severity}
  </span>
);

const AlertMark = ({ alert, now }: { readonly alert: Alert; readonly now: number }) => {
  if (alert.status === "resolved") {
    return <span className="alert__mark">Resolved {formatRelative(alert.resolved_at ?? alert.updated_at, now)}</span>;
  }
  return <span className="alert__mark">Acknowledged</span>;
};

const AlertRow = ({ alert, now, pending, onAcknowledge }: AlertRowProps) => {
  const acknowledged = alert.acknowledged_at !== null;
  const actionable = alert.status === "open" && !acknowledged && onAcknowledge !== null;
  return (
    <li
      className="alert"
      data-severity={alert.severity}
      data-status={alert.status}
      data-acknowledged={acknowledged}
      aria-label={describeAlert(alert)}
    >
      <div className="alert__head">
        <SeverityBadge severity={alert.severity} />
        <span className="alert__target">
          Switch {alert.dpid} · Port {alert.port_no}
        </span>
        <code className="alert__metric">{alert.metric}</code>
      </div>
      <dl className="alert__stats">
        <div className="alert__stat">
          <dt>Value</dt>
          <dd>{formatMetricValue(alert.metric, alert.value)}</dd>
        </div>
        <div className="alert__stat">
          <dt>Expected</dt>
          <dd>{formatMetricValue(alert.metric, alert.expected)}</dd>
        </div>
        <div className="alert__stat">
          <dt>z-score</dt>
          <dd>{formatZscore(alert.zscore)}</dd>
        </div>
        <div className="alert__stat">
          <dt>Opened</dt>
          <dd>
            <time dateTime={alert.opened_at}>{formatClock(alert.opened_at)}</time>{" "}
            <span className="alert__ago">{formatRelative(alert.opened_at, now)}</span>
          </dd>
        </div>
      </dl>
      <div className="alert__actions">
        {actionable ? (
          <button type="button" className="alert__ack" disabled={pending} onClick={() => onAcknowledge(alert.id)}>
            Acknowledge
          </button>
        ) : (
          <AlertMark alert={alert} now={now} />
        )}
      </div>
    </li>
  );
};

const ResolvedAlertsList = ({ resolved, now }: { readonly resolved: AlertsView["resolved"]; readonly now: number }) => {
  switch (resolved.kind) {
    case "hidden":
      return null;
    case "loading":
      return <p className="alerts__notice">Loading resolved alerts…</p>;
    case "unavailable":
      return (
        <p className="alerts__error" role="alert">
          {resolved.reason}
        </p>
      );
    case "ready":
      return resolved.alerts.length === 0 ? (
        <p className="alerts__notice">No resolved alerts</p>
      ) : (
        <ul className="alerts__list" aria-label="Resolved alerts">
          {resolved.alerts.map((alert) => (
            <AlertRow key={alert.id} alert={alert} now={now} pending={false} onAcknowledge={null} />
          ))}
        </ul>
      );
  }
};

export const AlertsPanel = ({
  alerts,
  summary,
  pending,
  error,
  acknowledge,
  resolved,
  toggleResolved,
  now = Date.now(),
}: AlertsPanelProps) => (
  <div className="alerts">
    <div className="alerts__counts">
      <span className="alerts__count" data-tone="critical">
        {summary.critical} critical
      </span>
      <span className="alerts__count" data-tone="warning">
        {summary.warning} warning
      </span>
      <span className="alerts__count" data-tone="neutral">
        {summary.acknowledged} acknowledged
      </span>
    </div>
    {error === null ? null : (
      <p className="alerts__error" role="alert">
        {error}
      </p>
    )}
    {alerts.length === 0 ? (
      <p className="alerts__empty">No open alerts</p>
    ) : (
      <ul className="alerts__list" aria-label="Open alerts">
        {alerts.map((alert) => (
          <AlertRow
            key={alert.id}
            alert={alert}
            now={now}
            pending={pending.has(alert.id)}
            onAcknowledge={(id) => void acknowledge(id)}
          />
        ))}
      </ul>
    )}
    <div className="alerts__footer">
      <button
        type="button"
        className="alerts__toggle"
        aria-pressed={resolved.kind !== "hidden"}
        onClick={toggleResolved}
      >
        {resolved.kind === "hidden" ? "Show resolved alerts" : "Hide resolved alerts"}
      </button>
    </div>
    <ResolvedAlertsList resolved={resolved} now={now} />
  </div>
);
