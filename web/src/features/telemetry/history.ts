import type { KpiSnapshot, PortKpis } from "./frames";

export type PortKey = `${number}:${number}`;

export type PortHistory = ReadonlyMap<PortKey, readonly PortKpis[]>;

export const emptyHistory: PortHistory = new Map();

export const portKey = (dpid: number, portNo: number): PortKey => `${dpid}:${portNo}`;

const appendPoint = (points: readonly PortKpis[], point: PortKpis, maxPoints: number): readonly PortKpis[] => {
  const last = points[points.length - 1];
  if (last !== undefined && last.computed_at === point.computed_at) {
    return points;
  }
  return [...points, point].slice(-maxPoints);
};

export const appendHistory = (history: PortHistory, snapshot: KpiSnapshot, maxPoints: number): PortHistory => {
  const next = new Map(history);
  for (const switchKpis of snapshot.switches) {
    for (const port of switchKpis.ports) {
      const key = portKey(port.dpid, port.port_no);
      next.set(key, appendPoint(next.get(key) ?? [], port, maxPoints));
    }
  }
  return next;
};
