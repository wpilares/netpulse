import type { AlertsFrame } from "../telemetry/frames";
import type { Alert } from "./alerts";

export const makeAlert = (overrides: Partial<Alert> = {}): Alert => ({
  id: 1,
  dpid: 1,
  port_no: 2,
  metric: "rx_bps",
  severity: "warning",
  status: "open",
  opened_at: "2026-10-26T10:00:00Z",
  last_seen_at: "2026-10-26T10:00:05Z",
  resolved_at: null,
  acknowledged_at: null,
  value: 9_400_000,
  expected: 1_200_000,
  zscore: 6.5,
  updated_at: "2026-10-26T10:00:05Z",
  ...overrides,
});

export const makeAlertsFrame = (alerts: readonly Alert[], generatedAt = "2026-10-26T10:00:05Z"): AlertsFrame => ({
  type: "alerts",
  generated_at: generatedAt,
  alerts,
});
