import { useQuery } from "@tanstack/react-query";
import { useApiClient } from "../../api/ApiClientProvider";
import { queryKeys } from "../../api/keys";
import { type ApiHealth, toApiHealth } from "./health";

export const HEALTH_POLL_INTERVAL_MS = 10_000;

export const useHealthQuery = (pollIntervalMs: number = HEALTH_POLL_INTERVAL_MS): ApiHealth => {
  const client = useApiClient();
  const { status, data } = useQuery({
    queryKey: queryKeys.health,
    queryFn: ({ signal }) => client.getHealth(signal),
    refetchInterval: pollIntervalMs,
  });
  return toApiHealth({ status, data });
};
