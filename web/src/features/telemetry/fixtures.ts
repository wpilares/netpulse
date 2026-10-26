import type { KpiFrame, KpiSnapshot, NetworkSummary, PortKpis, SwitchKpis } from "./frames";

export const makePort = (overrides: Partial<PortKpis> = {}): PortKpis => ({
  dpid: 1,
  port_no: 1,
  computed_at: "2026-10-26T10:00:00Z",
  interval_seconds: 5,
  rx_bps: 1_000_000,
  tx_bps: 500_000,
  rx_pps: 120,
  tx_pps: 60,
  drop_rate: 0,
  error_rate: 0,
  utilization: 0.1,
  counter_reset: false,
  ...overrides,
});

const sumOrNull = (values: readonly (number | null)[]): number | null => {
  const present = values.filter((value): value is number => value !== null);
  return present.length === 0 ? null : present.reduce((total, value) => total + value, 0);
};

const maxOrNull = (values: readonly (number | null)[]): number | null => {
  const present = values.filter((value): value is number => value !== null);
  return present.length === 0 ? null : Math.max(...present);
};

const summarize = (ports: readonly PortKpis[], switches: number): NetworkSummary => ({
  ports: ports.length,
  switches,
  rx_bps: sumOrNull(ports.map((port) => port.rx_bps)),
  tx_bps: sumOrNull(ports.map((port) => port.tx_bps)),
  drop_rate: maxOrNull(ports.map((port) => port.drop_rate)),
  error_rate: maxOrNull(ports.map((port) => port.error_rate)),
  max_utilization: maxOrNull(ports.map((port) => port.utilization)),
  counter_resets: ports.filter((port) => port.counter_reset).length,
});

export const makeSnapshot = (ports: readonly PortKpis[], generatedAt = "2026-10-26T10:00:00Z"): KpiSnapshot => {
  const byDpid = new Map<number, PortKpis[]>();
  for (const port of ports) {
    const group = byDpid.get(port.dpid) ?? [];
    group.push(port);
    byDpid.set(port.dpid, group);
  }
  const switches: SwitchKpis[] = [...byDpid.entries()].map(([dpid, switchPorts]) => ({
    dpid,
    generated_at: generatedAt,
    ports: switchPorts,
  }));
  return { generated_at: generatedAt, summary: summarize(ports, switches.length), switches };
};

export const makeKpiFrame = (ports: readonly PortKpis[], generatedAt = "2026-10-26T10:00:00Z"): KpiFrame => ({
  type: "kpis",
  ...makeSnapshot(ports, generatedAt),
});
