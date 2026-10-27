import { Radio } from "lucide-react";
import { useState } from "react";
import {
  Card,
  CardBody,
  CardHeader,
  CardTitle,
  EmptyState,
  SegmentedControl,
  type SegmentedOption,
} from "../../components/ui";
import type { KpiSnapshot } from "../telemetry/frames";
import { type PortHistory, portKey } from "../telemetry/history";
import { PortCard } from "./PortCard";
import styles from "./SwitchPortsPanel.module.css";

const HEADING_ID = "ports-heading";

export interface SwitchPortsPanelProps {
  readonly latest: KpiSnapshot | null;
  readonly history: PortHistory;
}

export const SwitchPortsPanel = ({ latest, history }: SwitchPortsPanelProps) => {
  const [selectedDpid, setSelectedDpid] = useState<string | null>(null);
  const switches = [...(latest?.switches ?? [])].sort((left, right) => left.dpid - right.dpid);
  const active = switches.find((entry) => String(entry.dpid) === selectedDpid) ?? switches[0];
  const options: readonly SegmentedOption<string>[] = switches.map((entry) => ({
    value: String(entry.dpid),
    label: `Switch ${entry.dpid}`,
  }));
  const ports = active === undefined ? [] : [...active.ports].sort((left, right) => left.port_no - right.port_no);

  return (
    <Card aria-labelledby={HEADING_ID}>
      <CardHeader
        actions={
          active === undefined ? undefined : (
            <SegmentedControl
              label="Switch"
              options={options}
              value={String(active.dpid)}
              onChange={setSelectedDpid}
              size="sm"
            />
          )
        }
      >
        <CardTitle id={HEADING_ID}>Switch ports</CardTitle>
      </CardHeader>
      <CardBody>
        {active === undefined ? (
          <EmptyState
            icon={Radio}
            title="No switches reporting yet"
            description="Port charts appear as soon as the controller publishes KPIs."
          />
        ) : (
          <div className={styles.grid}>
            {ports.map((port) => (
              <PortCard key={port.port_no} port={port} points={history.get(portKey(port.dpid, port.port_no)) ?? []} />
            ))}
          </div>
        )}
      </CardBody>
    </Card>
  );
};
