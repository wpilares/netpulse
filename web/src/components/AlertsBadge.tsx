import type { AlertSummary } from "../features/alerts/alerts";
import type { Tone } from "./tone";

export interface AlertsBadgeProps {
  readonly summary: AlertSummary;
}

interface BadgeView {
  readonly tone: Tone;
  readonly label: string;
  readonly detail: string | null;
}

const describeAlerts = ({ open, critical }: AlertSummary): BadgeView => {
  if (open === 0) {
    return { tone: "positive", label: "No alerts", detail: null };
  }
  return {
    tone: critical > 0 ? "critical" : "warning",
    label: open === 1 ? "1 alert" : `${open} alerts`,
    detail: critical > 0 ? `${critical} critical` : null,
  };
};

export const AlertsBadge = ({ summary }: AlertsBadgeProps) => {
  const { tone, label, detail } = describeAlerts(summary);
  return (
    <output className="alerts-badge" data-tone={tone} aria-live="polite">
      <span className="alerts-badge__dot" aria-hidden="true" />
      <span className="alerts-badge__label">{label}</span>
      {detail === null ? null : <span className="alerts-badge__detail">{detail}</span>}
    </output>
  );
};
