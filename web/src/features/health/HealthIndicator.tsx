import type { ApiHealth } from "./health";

type Tone = "neutral" | "positive" | "warning" | "critical";

interface IndicatorView {
  readonly tone: Tone;
  readonly label: string;
  readonly detail: string | null;
}

const describeHealth = (health: ApiHealth): IndicatorView => {
  switch (health.kind) {
    case "loading":
      return { tone: "neutral", label: "Checking API", detail: null };
    case "offline":
      return { tone: "critical", label: "API offline", detail: null };
    case "online": {
      const { status, database, version } = health.report;
      const detail = `database ${database} · v${version}`;
      return status === "ok"
        ? { tone: "positive", label: "API online", detail }
        : { tone: "warning", label: "API degraded", detail };
    }
  }
};

export interface HealthIndicatorProps {
  readonly health: ApiHealth;
}

export const HealthIndicator = ({ health }: HealthIndicatorProps) => {
  const { tone, label, detail } = describeHealth(health);
  return (
    <output className="health-indicator" data-tone={tone} aria-live="polite">
      <span className="health-indicator__dot" aria-hidden="true" />
      <span className="health-indicator__label">{label}</span>
      {detail === null ? null : <span className="health-indicator__detail">{detail}</span>}
    </output>
  );
};
