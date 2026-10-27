import { Card, CardBody, CardHeader, CardTitle, ErrorState } from "../../components/ui";
import { formatClock } from "../../lib/time";
import { SummaryGrid, SummarySkeleton } from "./SummaryGrid";
import styles from "./SummaryPanel.module.css";
import { type KpiSummaryState, useKpiSummaryState } from "./useKpiSummaryQuery";

const HEADING_ID = "summary-heading";

const SummaryBody = ({ snapshot, status, retry }: KpiSummaryState) => {
  if (snapshot !== null) {
    return <SummaryGrid summary={snapshot.summary} />;
  }
  if (status === "unavailable") {
    return (
      <ErrorState
        title="Network summary unavailable"
        description="The KPI summary could not be loaded from the API."
        onRetry={retry}
      />
    );
  }
  return <SummarySkeleton />;
};

export const SummaryPanelView = (state: KpiSummaryState) => (
  <Card aria-labelledby={HEADING_ID}>
    <CardHeader
      actions={
        state.snapshot === null ? undefined : (
          <span className={styles.updated}>
            Updated <time dateTime={state.snapshot.generated_at}>{formatClock(state.snapshot.generated_at)}</time>
          </span>
        )
      }
    >
      <CardTitle id={HEADING_ID}>Network summary</CardTitle>
    </CardHeader>
    <CardBody>
      <SummaryBody {...state} />
    </CardBody>
  </Card>
);

export const SummaryPanel = () => <SummaryPanelView {...useKpiSummaryState()} />;
