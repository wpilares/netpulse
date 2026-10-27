import { z } from "zod";

export const SERVICE_STATUSES = ["ok", "degraded"] as const;
export const DATABASE_STATES = ["up", "down", "disabled"] as const;
export const NODE_KINDS = ["switch", "host"] as const;
export const ALERT_METRICS = ["rx_bps", "tx_bps", "drop_rate", "error_rate"] as const;
export const SEVERITIES = ["warning", "critical"] as const;
export const ALERT_STATUSES = ["open", "resolved"] as const;

const nullableNumber = z.number().nullable();
const nullableString = z.string().nullable();

export const healthReportSchema = z
  .object({
    status: z.enum(SERVICE_STATUSES),
    database: z.enum(DATABASE_STATES),
    version: z.string(),
  })
  .readonly();

export const portKpisSchema = z
  .object({
    dpid: z.number(),
    port_no: z.number(),
    computed_at: z.string(),
    interval_seconds: z.number(),
    rx_bps: nullableNumber,
    tx_bps: nullableNumber,
    rx_pps: nullableNumber,
    tx_pps: nullableNumber,
    drop_rate: nullableNumber,
    error_rate: nullableNumber,
    utilization: nullableNumber,
    counter_reset: z.boolean(),
  })
  .readonly();

export const switchKpisSchema = z
  .object({
    dpid: z.number(),
    generated_at: z.string(),
    ports: z.array(portKpisSchema).readonly(),
  })
  .readonly();

export const networkSummarySchema = z
  .object({
    ports: z.number(),
    switches: z.number(),
    rx_bps: nullableNumber,
    tx_bps: nullableNumber,
    drop_rate: nullableNumber,
    error_rate: nullableNumber,
    max_utilization: nullableNumber,
    counter_resets: z.number(),
  })
  .readonly();

const kpiSnapshotShape = {
  generated_at: z.string(),
  summary: networkSummarySchema,
  switches: z.array(switchKpisSchema).readonly(),
};

export const kpiSnapshotSchema = z.object(kpiSnapshotShape).readonly();

export const topologyNodeSchema = z
  .object({
    id: z.string(),
    kind: z.enum(NODE_KINDS),
    dpid: nullableNumber,
    port_no: nullableNumber,
    label: z.string(),
  })
  .readonly();

export const topologyEdgeSchema = z
  .object({
    source: z.string(),
    target: z.string(),
    source_port: nullableNumber,
    target_port: nullableNumber,
  })
  .readonly();

export const topologySchema = z
  .object({
    generated_at: z.string(),
    nodes: z.array(topologyNodeSchema).readonly(),
    edges: z.array(topologyEdgeSchema).readonly(),
  })
  .readonly();

export const alertSchema = z
  .object({
    id: z.number(),
    dpid: z.number(),
    port_no: z.number(),
    metric: z.enum(ALERT_METRICS),
    severity: z.enum(SEVERITIES),
    status: z.enum(ALERT_STATUSES),
    opened_at: z.string(),
    last_seen_at: z.string(),
    resolved_at: nullableString,
    acknowledged_at: nullableString,
    value: z.number(),
    expected: z.number(),
    zscore: z.number(),
    updated_at: z.string(),
  })
  .readonly();

const alertListShape = {
  generated_at: z.string(),
  alerts: z.array(alertSchema).readonly(),
};

export const alertListSchema = z.object(alertListShape).readonly();

const kpiFrameSchema = z.object({ type: z.literal("kpis"), ...kpiSnapshotShape });
const alertsFrameSchema = z.object({ type: z.literal("alerts"), ...alertListShape });

export const liveFrameSchema = z
  .discriminatedUnion("type", [
    z.object({ type: z.literal("hello"), version: z.string() }),
    z.object({ type: z.literal("pong") }),
    z.object({ type: z.literal("error"), reason: z.string() }),
    z.object({ type: z.literal("heartbeat"), at: z.string() }),
    z.object({ type: z.literal("store_unavailable"), at: z.string() }),
    kpiFrameSchema,
    alertsFrameSchema,
  ])
  .readonly();

export type ServiceStatus = (typeof SERVICE_STATUSES)[number];
export type DatabaseState = (typeof DATABASE_STATES)[number];
export type NodeKind = (typeof NODE_KINDS)[number];
export type AlertMetric = (typeof ALERT_METRICS)[number];
export type Severity = (typeof SEVERITIES)[number];
export type AlertStatus = (typeof ALERT_STATUSES)[number];
export type AlertStatusFilter = AlertStatus | "all";

export type ApiHealthReport = z.infer<typeof healthReportSchema>;
export type PortKpis = z.infer<typeof portKpisSchema>;
export type SwitchKpis = z.infer<typeof switchKpisSchema>;
export type NetworkSummary = z.infer<typeof networkSummarySchema>;
export type KpiSnapshot = z.infer<typeof kpiSnapshotSchema>;
export type TopologyNode = z.infer<typeof topologyNodeSchema>;
export type TopologyEdge = z.infer<typeof topologyEdgeSchema>;
export type Topology = z.infer<typeof topologySchema>;
export type Alert = z.infer<typeof alertSchema>;
export type AlertList = z.infer<typeof alertListSchema>;
export type LiveFrame = z.infer<typeof liveFrameSchema>;
export type KpiFrame = Extract<LiveFrame, { readonly type: "kpis" }>;
export type AlertsFrame = Extract<LiveFrame, { readonly type: "alerts" }>;

export const parseWith =
  <T>(schema: z.ZodType<T>) =>
  (value: unknown): T | null => {
    const result = schema.safeParse(value);
    return result.success ? result.data : null;
  };
