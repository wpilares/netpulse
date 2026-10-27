import { useQueryClient } from "@tanstack/react-query";
import { useCallback } from "react";
import { queryKeys } from "../../api/keys";
import { useKpiSummaryQuery } from "../kpis/useKpiSummaryQuery";
import { TopologyView } from "./TopologyView";
import { useTopologyQuery } from "./useTopologyQuery";

export const TopologyPanel = () => {
  const queryClient = useQueryClient();
  const state = useTopologyQuery();
  const latest = useKpiSummaryQuery();
  const retry = useCallback(() => void queryClient.refetchQueries({ queryKey: queryKeys.topology }), [queryClient]);
  return <TopologyView state={state} latest={latest} onRetry={retry} />;
};
