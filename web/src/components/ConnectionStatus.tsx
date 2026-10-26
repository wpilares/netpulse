import type { SocketStatus } from "../features/telemetry/useTelemetrySocket";
import { formatClock } from "../lib/time";
import type { Tone } from "./tone";

export interface ConnectionStatusProps {
  readonly status: SocketStatus;
  readonly attempt: number;
  readonly storeUnavailable: boolean;
  readonly lastUpdateAt: string | null;
}

interface BadgeView {
  readonly tone: Tone;
  readonly label: string;
  readonly detail: string | null;
}

const describeConnection = ({ status, attempt, storeUnavailable, lastUpdateAt }: ConnectionStatusProps): BadgeView => {
  const detail = storeUnavailable
    ? "store unavailable"
    : lastUpdateAt === null
      ? null
      : `updated ${formatClock(lastUpdateAt)}`;
  switch (status) {
    case "connecting":
      return { tone: "neutral", label: "Connecting", detail };
    case "open":
      return { tone: storeUnavailable ? "warning" : "positive", label: "Live", detail };
    case "reconnecting":
      return { tone: "warning", label: `Reconnecting (attempt ${attempt})`, detail };
    case "closed":
      return { tone: "critical", label: "Disconnected", detail };
  }
};

export const ConnectionStatus = (props: ConnectionStatusProps) => {
  const { tone, label, detail } = describeConnection(props);
  return (
    <output className="connection-status" data-tone={tone} aria-live="polite">
      <span className="connection-status__dot" aria-hidden="true" />
      <span className="connection-status__label">{label}</span>
      {detail === null ? null : <span className="connection-status__detail">{detail}</span>}
    </output>
  );
};
