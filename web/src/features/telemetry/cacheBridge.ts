import type { QueryClient } from "@tanstack/react-query";
import { queryKeys } from "../../api/keys";
import type { AlertList, AlertsFrame, KpiFrame, KpiSnapshot, LiveFrame } from "../../api/schemas";
import { openAlerts, upsertAlerts } from "../alerts/alerts";

const openKey = queryKeys.alerts("open");

const applyKpiFrame = async (queryClient: QueryClient, frame: KpiFrame): Promise<void> => {
  await queryClient.cancelQueries({ queryKey: queryKeys.kpiSummary });
  queryClient.setQueryData<KpiSnapshot>(queryKeys.kpiSummary, frame);
};

const mergeAlerts = (current: AlertList | undefined, frame: AlertsFrame, alertsSynced: boolean): AlertList => {
  const base = alertsSynced ? (current?.alerts ?? []) : [];
  return { generated_at: frame.generated_at, alerts: openAlerts(upsertAlerts(base, frame.alerts)) };
};

const applyAlertsFrame = async (queryClient: QueryClient, frame: AlertsFrame, alertsSynced: boolean): Promise<void> => {
  await queryClient.cancelQueries({ queryKey: openKey });
  queryClient.setQueryData<AlertList>(openKey, (current) => mergeAlerts(current, frame, alertsSynced));
};

export const applyLiveFrame = async (
  queryClient: QueryClient,
  frame: LiveFrame,
  alertsSynced: boolean,
): Promise<void> => {
  switch (frame.type) {
    case "kpis":
      return applyKpiFrame(queryClient, frame);
    case "alerts":
      return applyAlertsFrame(queryClient, frame, alertsSynced);
    case "hello":
    case "pong":
    case "error":
    case "heartbeat":
    case "store_unavailable":
      return;
  }
};
