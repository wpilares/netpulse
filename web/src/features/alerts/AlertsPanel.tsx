import { AlertsPanelView } from "./AlertsPanelView";
import { useAlertsView } from "./useAlertsView";

export interface AlertsPanelProps {
  readonly alertsSynced: boolean;
}

export const AlertsPanel = ({ alertsSynced }: AlertsPanelProps) => (
  <AlertsPanelView {...useAlertsView({ alertsSynced })} />
);
