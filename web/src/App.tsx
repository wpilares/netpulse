import { AlertsBadge } from "./components/AlertsBadge";
import { ConnectionStatus } from "./components/ConnectionStatus";
import { AlertsPanel } from "./features/alerts/AlertsPanel";
import { useAlertsView } from "./features/alerts/useAlertsView";
import { ApiHealthStatus } from "./features/health/ApiHealthStatus";
import { SummaryCards } from "./features/kpis/SummaryCards";
import { SwitchPortsPanel } from "./features/kpis/SwitchPortsPanel";
import { useKpiSummaryQuery } from "./features/kpis/useKpiSummaryQuery";
import { useTelemetrySocket, type WebSocketLike } from "./features/telemetry/useTelemetrySocket";
import { TopologyView } from "./features/topology/TopologyView";
import { useTopologyQuery } from "./features/topology/useTopologyQuery";

export interface AppProps {
  readonly createSocket?: (url: string) => WebSocketLike;
  readonly socketUrl?: string;
}

export const App = ({ createSocket, socketUrl }: AppProps) => {
  const socket = useTelemetrySocket({
    ...(createSocket === undefined ? {} : { createSocket }),
    ...(socketUrl === undefined ? {} : { url: socketUrl }),
  });
  const snapshot = useKpiSummaryQuery();
  const topology = useTopologyQuery();
  const alerts = useAlertsView({ alertsSynced: socket.alertsSynced });

  return (
    <div className="shell">
      <header className="shell__header">
        <div>
          <h1 className="shell__title">NetPulse</h1>
          <p className="shell__subtitle">Real-time SDN network monitoring</p>
        </div>
        <div className="shell__badges">
          <ApiHealthStatus />
          <ConnectionStatus
            status={socket.status}
            attempt={socket.attempt}
            storeUnavailable={socket.storeUnavailable}
            lastUpdateAt={snapshot?.generated_at ?? socket.lastHeartbeatAt ?? null}
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
