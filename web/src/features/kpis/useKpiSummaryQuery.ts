import { useQuery } from "@tanstack/react-query";
import { useApiClient } from "../../api/ApiClientProvider";
import { queryKeys } from "../../api/keys";
import type { KpiSnapshot } from "../../api/schemas";

export type KpiSummaryStatus = "loading" | "unavailable" | "ready";

export interface KpiSummaryState {
  readonly snapshot: KpiSnapshot | null;
  readonly status: KpiSummaryStatus;
  readonly retry: () => void;
}

const toStatus = (data: KpiSnapshot | undefined, isError: boolean): KpiSummaryStatus => {
  if (data !== undefined) {
    return "ready";
  }
  return isError ? "unavailable" : "loading";
};

export const useKpiSummaryState = (): KpiSummaryState => {
  const client = useApiClient();
  const { data, isError, refetch } = useQuery({
    queryKey: queryKeys.kpiSummary,
    queryFn: ({ signal }) => client.getKpiSummary(signal),
  });
  return { snapshot: data ?? null, status: toStatus(data, isError), retry: () => void refetch() };
};

export const useKpiSummaryQuery = (): KpiSnapshot | null => useKpiSummaryState().snapshot;
