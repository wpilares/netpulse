import { kpiSnapshotSchema, liveFrameSchema, parseWith } from "../../api/schemas";

export type {
  AlertsFrame,
  KpiFrame,
  KpiSnapshot,
  LiveFrame,
  NetworkSummary,
  PortKpis,
  SwitchKpis,
} from "../../api/schemas";

export const parseKpiSnapshot = parseWith(kpiSnapshotSchema);

export const parseLiveFrame = parseWith(liveFrameSchema);
