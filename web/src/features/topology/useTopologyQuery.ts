import { useQuery } from "@tanstack/react-query";
import { useApiClient } from "../../api/ApiClientProvider";
import { queryKeys } from "../../api/keys";
import type { TopologyState } from "./topology";

export const TOPOLOGY_REFRESH_MS = 30_000;

export const useTopologyQuery = (refreshMs: number = TOPOLOGY_REFRESH_MS): TopologyState => {
  const client = useApiClient();
  const { status, data } = useQuery({
    queryKey: queryKeys.topology,
    queryFn: ({ signal }) => client.getTopology(signal),
    refetchInterval: refreshMs,
  });
  if (status === "error") {
    return { kind: "unavailable" };
  }
  if (data === undefined) {
    return { kind: "loading" };
  }
  return { kind: "ready", topology: data };
};
