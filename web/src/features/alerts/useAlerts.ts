import { useCallback, useEffect, useMemo, useState } from "react";
import {
  type Alert,
  type AlertSummary,
  acknowledgeAlert,
  alertSummary,
  describeAlertError,
  fetchAlerts,
  openAlerts,
} from "./alerts";

const OPEN_LIMIT = 100;
const RESOLVED_LIMIT = 50;

export interface LiveAlerts {
  readonly alerts: readonly Alert[];
  readonly alertsSynced: boolean;
}

export type ResolvedAlerts =
  | { readonly kind: "hidden" }
  | { readonly kind: "loading" }
  | { readonly kind: "ready"; readonly alerts: readonly Alert[] }
  | { readonly kind: "unavailable"; readonly reason: string };

type ResolvedResult = Exclude<ResolvedAlerts, { kind: "hidden" } | { kind: "loading" }>;

export interface AlertsView {
  readonly alerts: readonly Alert[];
  readonly summary: AlertSummary;
  readonly pending: ReadonlySet<number>;
  readonly error: string | null;
  readonly acknowledge: (id: number) => Promise<void>;
  readonly resolved: ResolvedAlerts;
  readonly toggleResolved: () => void;
}

const isoNow = (): string => new Date().toISOString();

const withAcknowledgements = (alerts: readonly Alert[], acknowledged: ReadonlyMap<number, string>): Alert[] =>
  alerts.map((alert) => {
    const at = acknowledged.get(alert.id);
    return alert.acknowledged_at === null && at !== undefined ? { ...alert, acknowledged_at: at } : alert;
  });

const without = <K, V>(entries: ReadonlyMap<K, V>, key: K): Map<K, V> => {
  const next = new Map(entries);
  next.delete(key);
  return next;
};

const withoutMember = <T>(members: ReadonlySet<T>, member: T): Set<T> => {
  const next = new Set(members);
  next.delete(member);
  return next;
};

export const useAlerts = (fetcher: typeof fetch, live: LiveAlerts, clock: () => string = isoNow): AlertsView => {
  const [fetched, setFetched] = useState<readonly Alert[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [acknowledged, setAcknowledged] = useState<ReadonlyMap<number, string>>(new Map());
  const [pending, setPending] = useState<ReadonlySet<number>>(new Set());
  const [showResolved, setShowResolved] = useState(false);
  const [resolvedResult, setResolvedResult] = useState<ResolvedResult | null>(null);

  useEffect(() => {
    if (live.alertsSynced) {
      return;
    }
    const controller = new AbortController();
    void fetchAlerts(fetcher, { status: "open", limit: OPEN_LIMIT, signal: controller.signal }).then(
      (list) => {
        if (!controller.signal.aborted) {
          setFetched(list.alerts);
          setError(null);
        }
      },
      (failure: unknown) => {
        if (!controller.signal.aborted) {
          setError(describeAlertError(failure));
        }
      },
    );
    return () => controller.abort();
  }, [fetcher, live.alertsSynced]);

  useEffect(() => {
    if (!showResolved) {
      return;
    }
    const controller = new AbortController();
    void fetchAlerts(fetcher, { status: "resolved", limit: RESOLVED_LIMIT, signal: controller.signal }).then(
      (list) => {
        if (!controller.signal.aborted) {
          setResolvedResult({ kind: "ready", alerts: list.alerts });
        }
      },
      (failure: unknown) => {
        if (!controller.signal.aborted) {
          setResolvedResult({ kind: "unavailable", reason: describeAlertError(failure) });
        }
      },
    );
    return () => controller.abort();
  }, [fetcher, showResolved]);

  const acknowledge = useCallback(
    async (id: number): Promise<void> => {
      const optimisticAt = clock();
      setAcknowledged((current) => new Map(current).set(id, optimisticAt));
      setPending((current) => new Set(current).add(id));
      try {
        const alert = await acknowledgeAlert(fetcher, id);
        setAcknowledged((current) => new Map(current).set(id, alert.acknowledged_at ?? optimisticAt));
        setError(null);
      } catch (failure: unknown) {
        setAcknowledged((current) => without(current, id));
        setError(describeAlertError(failure));
      } finally {
        setPending((current) => withoutMember(current, id));
      }
    },
    [fetcher, clock],
  );

  const toggleResolved = useCallback(() => {
    setShowResolved((current) => !current);
    setResolvedResult(null);
  }, []);

  const base = live.alertsSynced ? live.alerts : fetched;
  const alerts = useMemo(() => withAcknowledgements(openAlerts(base), acknowledged), [base, acknowledged]);
  const summary = useMemo(() => alertSummary(alerts), [alerts]);
  const resolved: ResolvedAlerts = showResolved ? (resolvedResult ?? { kind: "loading" }) : { kind: "hidden" };

  return { alerts, summary, pending, error, acknowledge, resolved, toggleResolved };
};
