import { useMutation, useMutationState, useQueryClient } from "@tanstack/react-query";
import { useCallback, useMemo } from "react";
import { useApiClient } from "../../api/ApiClientProvider";
import { mutationKeys, queryKeys } from "../../api/keys";
import type { Alert, AlertList } from "../../api/schemas";
import { describeAlertError, upsertAlerts } from "./alerts";

const openKey = queryKeys.alerts("open");

export interface AcknowledgeAlert {
  readonly acknowledge: (id: number) => Promise<void>;
  readonly pending: ReadonlySet<number>;
  readonly error: string | null;
}

interface AcknowledgeContext {
  readonly previousAt: string | null;
}

const isoNow = (): string => new Date().toISOString();

const withAcknowledgedAt = (list: AlertList | undefined, id: number, at: string | null): AlertList | undefined =>
  list === undefined
    ? undefined
    : { ...list, alerts: list.alerts.map((alert) => (alert.id === id ? { ...alert, acknowledged_at: at } : alert)) };

const withAlert = (list: AlertList | undefined, alert: Alert): AlertList | undefined =>
  list === undefined ? undefined : { ...list, alerts: upsertAlerts(list.alerts, [alert]) };

const noop = (): undefined => undefined;

export const useAcknowledgeAlert = (clock: () => string = isoNow): AcknowledgeAlert => {
  const client = useApiClient();
  const queryClient = useQueryClient();

  const mutation = useMutation<Alert, unknown, number, AcknowledgeContext>({
    mutationKey: mutationKeys.acknowledgeAlert,
    mutationFn: (id) => client.acknowledgeAlert(id),
    onMutate: async (id) => {
      await queryClient.cancelQueries({ queryKey: openKey });
      const current = queryClient.getQueryData<AlertList>(openKey);
      const previousAt = current?.alerts.find((alert) => alert.id === id)?.acknowledged_at ?? null;
      queryClient.setQueryData<AlertList>(openKey, (list) => withAcknowledgedAt(list, id, clock()));
      return { previousAt };
    },
    onError: (_error, id, context) => {
      queryClient.setQueryData<AlertList>(openKey, (list) => withAcknowledgedAt(list, id, context?.previousAt ?? null));
    },
    onSuccess: (alert) => {
      queryClient.setQueryData<AlertList>(openKey, (list) => withAlert(list, alert));
    },
  });

  const pendingIds = useMutationState({
    filters: { mutationKey: mutationKeys.acknowledgeAlert, status: "pending" },
    select: (pendingMutation) => pendingMutation.state.variables,
  });
  const pending = useMemo(() => new Set(pendingIds.filter((id): id is number => typeof id === "number")), [pendingIds]);

  const { mutateAsync } = mutation;
  const acknowledge = useCallback((id: number) => mutateAsync(id).then(noop, noop), [mutateAsync]);
  const error = mutation.error === null ? null : describeAlertError(mutation.error);

  return { acknowledge, pending, error };
};
