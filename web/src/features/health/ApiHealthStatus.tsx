import { HealthIndicator } from "./HealthIndicator";
import { HEALTH_POLL_INTERVAL_MS, useHealthQuery } from "./useHealthQuery";

export interface ApiHealthStatusProps {
  readonly pollIntervalMs?: number;
}

export const ApiHealthStatus = ({ pollIntervalMs = HEALTH_POLL_INTERVAL_MS }: ApiHealthStatusProps) => {
  const health = useHealthQuery(pollIntervalMs);
  return <HealthIndicator health={health} />;
};
