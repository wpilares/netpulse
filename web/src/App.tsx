import { ApiHealthStatus } from "./features/health/ApiHealthStatus";

export const App = () => (
  <div className="shell">
    <header className="shell__header">
      <div>
        <h1 className="shell__title">NetPulse</h1>
        <p className="shell__subtitle">Real-time SDN network monitoring</p>
      </div>
      <ApiHealthStatus />
    </header>
    <main className="shell__main">
      <section className="panel" aria-labelledby="telemetry-heading">
        <h2 id="telemetry-heading">Live telemetry</h2>
        <p>Port and flow statistics will stream here once telemetry ingestion lands.</p>
      </section>
    </main>
  </div>
);
