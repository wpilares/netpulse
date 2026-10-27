import type { QueryClient } from "@tanstack/react-query";
import { queryKeys } from "../../api/keys";
import type { AlertList, AlertsFrame, KpiFrame, KpiSnapshot, LiveFrame } from "../../api/schemas";
import { openAlerts, upsertAlerts } from "../alerts/alerts";

const openKey = queryKeys.alerts("open");

const applyKpiFrame = (queryClient: QueryClient, frame: KpiFrame): void => {
  void queryClient.cancelQueries({ queryKey: queryKeys.kpiSummary });
  queryClient.setQueryData<KpiSnapshot>(queryKeys.kpiSummary, frame);
};

const mergeAlerts = (current: AlertList | undefined, frame: AlertsFrame, alertsSynced: boolean): AlertList => {
  const base = alertsSynced ? (current?.alerts ?? []) : [];
  return { generated_at: frame.generated_at, alerts: openAlerts(upsertAlerts(base, frame.alerts)) };
};

const applyAlertsFrame = (queryClient: QueryClient, frame: AlertsFrame, alertsSynced: boolean): void => {
  void queryClient.cancelQueries({ queryKey: openKey });
  queryClient.setQueryData<AlertList>(openKey, (current) => mergeAlerts(current, frame, alertsSynced));
};

export const applyLiveFrame = (queryClient: QueryClient, frame: LiveFrame, alertsSynced: boolean): void => {
  switch (frame.type) {
    case "kpis":
      applyKpiFrame(queryClient, frame);
      return;
    case "alerts":
      applyAlertsFrame(queryClient, frame, alertsSynced);
      return;
    case "hello":
    case "pong":
    case "error":
    case "heartbeat":
    case "store_unavailable":
      return;
  }
};
