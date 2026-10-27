import { useQuery } from "@tanstack/react-query";
import { useApiClient } from "../../api/ApiClientProvider";
import { queryKeys } from "../../api/keys";
import type { KpiSnapshot } from "../../api/schemas";

export const useKpiSummaryQuery = (): KpiSnapshot | null => {
  const client = useApiClient();
  const { data } = useQuery({
    queryKey: queryKeys.kpiSummary,
    queryFn: ({ signal }) => client.getKpiSummary(signal),
  });
  return data ?? null;
};
