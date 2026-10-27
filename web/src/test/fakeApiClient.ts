import { type Mock, vi } from "vitest";
import type { ApiClient } from "../api/client";
import { makeAlert } from "../features/alerts/fixtures";
import { makePort, makeSnapshot } from "../features/telemetry/fixtures";
import { makeTopology } from "../features/topology/fixtures";

export type FakeApiClient = { readonly [Method in keyof ApiClient]: Mock<ApiClient[Method]> };

const defaults: ApiClient = {
  getHealth: () => Promise.resolve({ status: "ok", database: "up", version: "1.0.0" }),
  getKpiSummary: () => Promise.resolve(makeSnapshot([makePort()])),
  getTopology: () => Promise.resolve(makeTopology()),
  listAlerts: () => Promise.resolve({ generated_at: "2026-10-26T10:00:00Z", alerts: [] }),
  acknowledgeAlert: (id) => Promise.resolve(makeAlert({ id, acknowledged_at: "2026-10-26T10:03:00Z" })),
};

export const createFakeApiClient = (overrides: Partial<ApiClient> = {}): FakeApiClient => ({
  getHealth: vi.fn(overrides.getHealth ?? defaults.getHealth),
  getKpiSummary: vi.fn(overrides.getKpiSummary ?? defaults.getKpiSummary),
  getTopology: vi.fn(overrides.getTopology ?? defaults.getTopology),
  listAlerts: vi.fn(overrides.listAlerts ?? defaults.listAlerts),
  acknowledgeAlert: vi.fn(overrides.acknowledgeAlert ?? defaults.acknowledgeAlert),
});
