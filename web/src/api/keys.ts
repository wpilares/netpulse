import type { AlertStatusFilter } from "./schemas";

export const queryKeys = {
  health: ["health"] as const,
  kpiSummary: ["kpis", "summary"] as const,
  topology: ["topology"] as const,
  alerts: (status: AlertStatusFilter) => ["alerts", status] as const,
};

export const mutationKeys = {
  acknowledgeAlert: ["alerts", "acknowledge"] as const,
};
