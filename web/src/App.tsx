import { AlertsBadge } from "./components/AlertsBadge";
import { ConnectionStatus } from "./components/ConnectionStatus";
import { AlertsPanel } from "./features/alerts/AlertsPanel";
import { useAlerts } from "./features/alerts/useAlerts";
import { ApiHealthStatus } from "./features/health/ApiHealthStatus";
import { SummaryCards } from "./features/kpis/SummaryCards";
import { SwitchPortsPanel } from "./features/kpis/SwitchPortsPanel";
import { useKpiSummary } from "./features/kpis/summary";
import { useTelemetrySocket, type WebSocketLike } from "./features/telemetry/useTelemetrySocket";
import { TopologyView } from "./features/topology/TopologyView";
import { useTopology } from "./features/topology/topology";

const TOPOLOGY_REFRESH_MS = 30_000;

const browserFetch: typeof fetch = (input, init) => fetch(input, init);

export interface AppProps {
  readonly fetcher?: typeof fetch;
  readonly createSocket?: (url: string) => WebSocketLike;
  readonly socketUrl?: string;
}

export const App = ({ fetcher = browserFetch, createSocket, socketUrl }: AppProps) => {
  const socket = useTelemetrySocket({
    ...(createSocket === undefined ? {} : { createSocket }),
    ...(socketUrl === undefined ? {} : { url: socketUrl }),
  });
  const initialSummary = useKpiSummary(fetcher);
  const topology = useTopology(fetcher, TOPOLOGY_REFRESH_MS);
  const alerts = useAlerts(fetcher, socket);
  const snapshot = socket.latest ?? initialSummary;

  return (
    <div className="shell">
      <header className="shell__header">
        <div>
          <h1 className="shell__title">NetPulse</h1>
          <p className="shell__subtitle">Real-time SDN network monitoring</p>
        </div>
        <div className="shell__badges">
          <ApiHealthStatus fetcher={fetcher} />
          <ConnectionStatus
            status={socket.status}
            attempt={socket.attempt}
            storeUnavailable={socket.storeUnavailable}
            lastUpdateAt={socket.latest?.generated_at ?? socket.lastHeartbeatAt ?? snapshot?.generated_at ?? null}
          />
          <AlertsBadge summary={alerts.summary} />
        </div>
      </header>
      <main className="shell__main">
        <section className="panel" aria-labelledby="summary-heading">
          <h2 id="summary-heading">Network summary</h2>
          <SummaryCards summary={snapshot?.summary ?? null} />
        </section>
        <section className="panel" aria-labelledby="alerts-heading">
          <h2 id="alerts-heading">Alerts</h2>
          <AlertsPanel {...alerts} />
        </section>
        <section className="panel" aria-labelledby="topology-heading">
          <h2 id="topology-heading">Topology</h2>
          <TopologyView state={topology} latest={snapshot} />
        </section>
        <section className="panel" aria-labelledby="ports-heading">
          <h2 id="ports-heading">Switch ports</h2>
          <SwitchPortsPanel latest={snapshot} history={socket.history} />
        </section>
      </main>
    </div>
  );
};
