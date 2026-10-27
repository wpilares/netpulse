import { AppShell } from "./app/AppShell";
import { AlertsBadge } from "./components/AlertsBadge";
import { ConnectionStatus } from "./components/ConnectionStatus";
import { AlertsPanel } from "./features/alerts/AlertsPanel";
import { useAlertsQuery } from "./features/alerts/useAlertsQuery";
import { ApiHealthStatus } from "./features/health/ApiHealthStatus";
import { useHealthQuery } from "./features/health/useHealthQuery";
import { SummaryPanel } from "./features/kpis/SummaryPanel";
import { SwitchPortsPanel } from "./features/kpis/SwitchPortsPanel";
import { useKpiSummaryQuery } from "./features/kpis/useKpiSummaryQuery";
import { useTelemetrySocket, type WebSocketLike } from "./features/telemetry/useTelemetrySocket";
import { TopologyPanel } from "./features/topology/TopologyPanel";

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
  const health = useHealthQuery();
  const { summary } = useAlertsQuery({ alertsSynced: socket.alertsSynced });

  return (
    <AppShell
      status={
        <>
          <ApiHealthStatus />
          <ConnectionStatus
            status={socket.status}
            attempt={socket.attempt}
            storeUnavailable={socket.storeUnavailable}
            lastUpdateAt={snapshot?.generated_at ?? socket.lastHeartbeatAt ?? null}
          />
          <AlertsBadge summary={summary} />
        </>
      }
      version={health.kind === "online" ? health.report.version : null}
      summary={<SummaryPanel />}
      alerts={<AlertsPanel alertsSynced={socket.alertsSynced} />}
      topology={<TopologyPanel />}
      ports={<SwitchPortsPanel latest={snapshot} history={socket.history} />}
    />
  );
};
