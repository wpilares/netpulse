import { HealthIndicator } from "./HealthIndicator";
import { useApiHealth } from "./useApiHealth";

const DEFAULT_POLL_INTERVAL_MS = 10_000;

const browserFetch: typeof fetch = (input, init) => fetch(input, init);

export interface ApiHealthStatusProps {
  readonly fetcher?: typeof fetch;
  readonly pollIntervalMs?: number;
}

export const ApiHealthStatus = ({
  fetcher = browserFetch,
  pollIntervalMs = DEFAULT_POLL_INTERVAL_MS,
}: ApiHealthStatusProps) => {
  const health = useApiHealth(fetcher, pollIntervalMs);
  return <HealthIndicator health={health} />;
};
