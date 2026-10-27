import { useQuery } from "@tanstack/react-query";
import { useCallback, useMemo, useState } from "react";
import { useApiClient } from "../../api/ApiClientProvider";
import { queryKeys } from "../../api/keys";
import type { Alert, AlertList } from "../../api/schemas";
import { type AlertSummary, alertSummary, describeAlertError, openAlerts } from "./alerts";

const OPEN_LIMIT = 100;
const RESOLVED_LIMIT = 50;

const noAlerts: readonly Alert[] = [];

export interface AlertsQueryOptions {
  readonly alertsSynced: boolean;
}

export type ResolvedAlerts =
  | { readonly kind: "hidden" }
  | { readonly kind: "loading" }
  | { readonly kind: "ready"; readonly alerts: readonly Alert[] }
  | { readonly kind: "unavailable"; readonly reason: string };

export interface AlertsQuery {
  readonly alerts: readonly Alert[];
  readonly summary: AlertSummary;
  readonly error: string | null;
  readonly resolved: ResolvedAlerts;
  readonly toggleResolved: () => void;
}

export const useAlertsQuery = ({ alertsSynced }: AlertsQueryOptions): AlertsQuery => {
  const client = useApiClient();
  const [showResolved, setShowResolved] = useState(false);

  const open = useQuery({
    queryKey: queryKeys.alerts("open"),
    queryFn: ({ signal }) => client.listAlerts({ status: "open", limit: OPEN_LIMIT }, signal),
    enabled: !alertsSynced,
  });

  const resolvedQuery = useQuery({
    queryKey: queryKeys.alerts("resolved"),
    queryFn: ({ signal }) => client.listAlerts({ status: "resolved", limit: RESOLVED_LIMIT }, signal),
    enabled: showResolved,
  });

  const toggleResolved = useCallback(() => setShowResolved((current) => !current), []);

  const alerts = useMemo(() => openAlerts(open.data?.alerts ?? noAlerts), [open.data]);
  const summary = useMemo(() => alertSummary(alerts), [alerts]);
  const error = open.error === null ? null : describeAlertError(open.error);

  const resolved = showResolved ? resolvedView(resolvedQuery.data, resolvedQuery.error) : hidden;

  return { alerts, summary, error, resolved, toggleResolved };
};

const hidden: ResolvedAlerts = { kind: "hidden" };

const resolvedView = (data: AlertList | undefined, error: unknown): ResolvedAlerts => {
  if (data !== undefined) {
    return { kind: "ready", alerts: data.alerts };
  }
  if (error !== null) {
    return { kind: "unavailable", reason: describeAlertError(error) };
  }
  return { kind: "loading" };
};
