import { useState } from "react";
import type { KpiSnapshot, PortKpis } from "../telemetry/frames";
import { type PortHistory, portKey } from "../telemetry/history";
import { formatPps, formatRate } from "./chart";
import { PortChart } from "./PortChart";

export interface SwitchPortsPanelProps {
  readonly latest: KpiSnapshot | null;
  readonly history: PortHistory;
}

const PortCard = ({ port, points }: { readonly port: PortKpis; readonly points: readonly PortKpis[] }) => (
  <article className="port" data-reset={port.counter_reset}>
    <header className="port__header">
      <h3 className="port__title">Port {port.port_no}</h3>
      {port.counter_reset ? <span className="port__flag">Counter reset</span> : null}
    </header>
    <p className="port__stats">
      <span>utilization {formatRate(port.utilization)}</span>
      <span>drops {formatRate(port.drop_rate)}</span>
      <span>errors {formatRate(port.error_rate)}</span>
      <span>
        {formatPps(port.rx_pps)} in · {formatPps(port.tx_pps)} out
      </span>
    </p>
    <PortChart portNo={port.port_no} points={points} />
  </article>
);

export const SwitchPortsPanel = ({ latest, history }: SwitchPortsPanelProps) => {
  const [selectedDpid, setSelectedDpid] = useState<number | null>(null);
  const switches = [...(latest?.switches ?? [])].sort((left, right) => left.dpid - right.dpid);
  const active = switches.find((entry) => entry.dpid === selectedDpid) ?? switches[0];

  if (active === undefined) {
    return <p className="ports__notice">No switches reporting yet.</p>;
  }

  const ports = [...active.ports].sort((left, right) => left.port_no - right.port_no);

  return (
    <div className="ports">
      <fieldset className="ports__switches">
        <legend className="ports__legend">Switches</legend>
        {switches.map((entry) => (
          <button
            key={entry.dpid}
            type="button"
            className="ports__switch"
            aria-pressed={entry.dpid === active.dpid}
            onClick={() => setSelectedDpid(entry.dpid)}
          >
            Switch {entry.dpid}
          </button>
        ))}
      </fieldset>
      <div className="ports__grid">
        {ports.map((port) => (
          <PortCard key={port.port_no} port={port} points={history.get(portKey(port.dpid, port.port_no)) ?? []} />
        ))}
      </div>
    </div>
  );
};
