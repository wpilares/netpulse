import {
  Badge,
  Card,
  CardBody,
  CardHeader,
  CardTitle,
  ErrorState,
  SegmentedControl,
  type SegmentedOption,
  Skeleton,
  VisuallyHidden,
} from "../../components/ui";
import { AlertsList } from "./AlertsList";
import styles from "./AlertsPanelView.module.css";
import type { AlertFilter } from "./alerts";
import type { AlertsView, ResolvedAlerts } from "./useAlertsView";

const HEADING_ID = "alerts-heading";

const filterOptions: readonly SegmentedOption<AlertFilter>[] = [
  { value: "open", label: "Open" },
  { value: "resolved", label: "Resolved" },
];

export interface AlertsPanelViewProps extends AlertsView {
  readonly now?: number;
}

const ResolvedBody = ({ resolved, now }: { readonly resolved: ResolvedAlerts; readonly now: number }) => {
  switch (resolved.kind) {
    case "hidden":
      return null;
    case "loading":
      return (
        <div className={styles.loading} aria-busy="true">
          <VisuallyHidden>Loading resolved alerts…</VisuallyHidden>
          <Skeleton height="4.5rem" />
          <Skeleton height="4.5rem" />
        </div>
      );
    case "unavailable":
      return <ErrorState title="Resolved alerts unavailable" description={resolved.reason} />;
    case "ready":
      return (
        <AlertsList
          label="Resolved alerts"
          alerts={resolved.alerts}
          now={now}
          emptyTitle="No resolved alerts"
          emptyDescription="Alerts that close will appear here."
        />
      );
  }
};

export const AlertsPanelView = ({
  alerts,
  summary,
  pending,
  error,
  acknowledge,
  filter,
  setFilter,
  resolved,
  now = Date.now(),
}: AlertsPanelViewProps) => (
  <Card aria-labelledby={HEADING_ID}>
    <CardHeader
      actions={
        <SegmentedControl label="Alert status" options={filterOptions} value={filter} onChange={setFilter} size="sm" />
      }
    >
      <CardTitle id={HEADING_ID}>Alerts</CardTitle>
      <div className={styles.counts}>
        <Badge tone="critical">{summary.critical} critical</Badge>
        <Badge tone="warning">{summary.warning} warning</Badge>
        <Badge tone="neutral">{summary.acknowledged} acknowledged</Badge>
      </div>
    </CardHeader>
    <CardBody>
      {error === null ? null : <ErrorState title="Alerts unavailable" description={error} />}
      {filter === "open" ? (
        <AlertsList
          label="Open alerts"
          alerts={alerts}
          now={now}
          pending={pending}
          onAcknowledge={(id) => void acknowledge(id)}
          emptyTitle="No open alerts"
          emptyDescription="Anomalies detected on switch ports will show up here."
        />
      ) : (
        <ResolvedBody resolved={resolved} now={now} />
      )}
    </CardBody>
  </Card>
);
