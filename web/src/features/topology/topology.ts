import { useEffect, useState } from "react";
import { isArrayOf, isNullableNumber, isOneOf, isRecord } from "../../lib/guards";
import type { KpiSnapshot } from "../telemetry/frames";
import { type PortKey, portKey } from "../telemetry/history";

const TOPOLOGY_PATH = "/api/v1/topology";
const NODE_KINDS = ["switch", "host"] as const;
const VERTICAL_PADDING = 48;

export type NodeKind = (typeof NODE_KINDS)[number];

export interface TopologyNode {
  readonly id: string;
  readonly kind: NodeKind;
  readonly dpid: number | null;
  readonly port_no: number | null;
  readonly label: string;
}

export interface TopologyEdge {
  readonly source: string;
  readonly target: string;
  readonly source_port: number | null;
  readonly target_port: number | null;
}

export interface Topology {
  readonly generated_at: string;
  readonly nodes: readonly TopologyNode[];
  readonly edges: readonly TopologyEdge[];
}

export type TopologyState =
  | { readonly kind: "loading" }
  | { readonly kind: "unavailable" }
  | { readonly kind: "ready"; readonly topology: Topology };

export interface PositionedNode extends TopologyNode {
  readonly x: number;
  readonly y: number;
  readonly depth: number;
}

export interface PositionedEdge extends TopologyEdge {
  readonly x1: number;
  readonly y1: number;
  readonly x2: number;
  readonly y2: number;
}

export interface TopologyLayout {
  readonly width: number;
  readonly height: number;
  readonly nodes: readonly PositionedNode[];
  readonly edges: readonly PositionedEdge[];
}

export type UtilizationLevel = "unknown" | "idle" | "low" | "medium" | "high" | "saturated";

const parseNode = (value: unknown): TopologyNode | null => {
  if (!isRecord(value)) {
    return null;
  }
  const { id, kind, dpid, port_no, label } = value;
  if (
    typeof id !== "string" ||
    !isOneOf(NODE_KINDS, kind) ||
    !isNullableNumber(dpid) ||
    !isNullableNumber(port_no) ||
    typeof label !== "string"
  ) {
    return null;
  }
  return { id, kind, dpid, port_no, label };
};

const parseEdge = (value: unknown): TopologyEdge | null => {
  if (!isRecord(value)) {
    return null;
  }
  const { source, target, source_port, target_port } = value;
  if (
    typeof source !== "string" ||
    typeof target !== "string" ||
    !isNullableNumber(source_port) ||
    !isNullableNumber(target_port)
  ) {
    return null;
  }
  return { source, target, source_port, target_port };
};

const isNode = (value: unknown): value is TopologyNode => parseNode(value) !== null;
const isEdge = (value: unknown): value is TopologyEdge => parseEdge(value) !== null;

export const parseTopology = (value: unknown): Topology | null => {
  if (!isRecord(value)) {
    return null;
  }
  const { generated_at, nodes, edges } = value;
  if (typeof generated_at !== "string" || !isArrayOf(nodes, isNode) || !isArrayOf(edges, isEdge)) {
    return null;
  }
  return { generated_at, nodes, edges };
};

export const fetchTopology = async (fetcher: typeof fetch, signal?: AbortSignal): Promise<TopologyState> => {
  try {
    const response = await fetcher(TOPOLOGY_PATH, {
      headers: { Accept: "application/json" },
      ...(signal === undefined ? {} : { signal }),
    });
    if (!response.ok) {
      return { kind: "unavailable" };
    }
    const topology = parseTopology(await response.json());
    return topology === null ? { kind: "unavailable" } : { kind: "ready", topology };
  } catch {
    return { kind: "unavailable" };
  }
};

export const useTopology = (fetcher: typeof fetch, refreshMs: number): TopologyState => {
  const [state, setState] = useState<TopologyState>({ kind: "loading" });

  useEffect(() => {
    const controller = new AbortController();
    const refresh = async () => {
      const next = await fetchTopology(fetcher, controller.signal);
      if (!controller.signal.aborted) {
        setState(next);
      }
    };
    void refresh();
    const timer = window.setInterval(() => void refresh(), refreshMs);
    return () => {
      controller.abort();
      window.clearInterval(timer);
    };
  }, [fetcher, refreshMs]);

  return state;
};

const compareNodes = (left: TopologyNode, right: TopologyNode): number => {
  if (left.dpid !== right.dpid) {
    if (left.dpid === null) {
      return 1;
    }
    if (right.dpid === null) {
      return -1;
    }
    return left.dpid - right.dpid;
  }
  if (left.port_no !== right.port_no) {
    if (left.port_no === null) {
      return 1;
    }
    if (right.port_no === null) {
      return -1;
    }
    return left.port_no - right.port_no;
  }
  return left.id.localeCompare(right.id);
};

const compareEdges = (left: TopologyEdge, right: TopologyEdge): number =>
  left.source.localeCompare(right.source) || left.target.localeCompare(right.target);

const spread = (index: number, count: number, width: number): number => (width * (index + 1)) / (count + 1);

const rowY = (row: number, rows: number, height: number): number => {
  if (rows <= 1) {
    return height / 2;
  }
  return VERTICAL_PADDING + (row * (height - 2 * VERTICAL_PADDING)) / (rows - 1);
};

const switchDepths = (switches: readonly TopologyNode[], edges: readonly TopologyEdge[]): Map<string, number> => {
  const switchIds = new Set(switches.map((node) => node.id));
  const neighbours = new Map<string, Set<string>>();
  for (const edge of edges) {
    if (!switchIds.has(edge.source) || !switchIds.has(edge.target)) {
      continue;
    }
    neighbours.set(edge.source, (neighbours.get(edge.source) ?? new Set()).add(edge.target));
    neighbours.set(edge.target, (neighbours.get(edge.target) ?? new Set()).add(edge.source));
  }
  const depths = new Map<string, number>();
  for (const root of switches) {
    if (depths.has(root.id)) {
      continue;
    }
    depths.set(root.id, 0);
    const queue = [root.id];
    for (let head = 0; head < queue.length; head += 1) {
      const current = queue[head];
      if (current === undefined) {
        break;
      }
      const depth = depths.get(current) ?? 0;
      for (const next of [...(neighbours.get(current) ?? [])].sort()) {
        if (!depths.has(next)) {
          depths.set(next, depth + 1);
          queue.push(next);
        }
      }
    }
  }
  return depths;
};

const hostParents = (hosts: readonly TopologyNode[], edges: readonly TopologyEdge[]): Map<string, string> => {
  const hostIds = new Set(hosts.map((node) => node.id));
  const parents = new Map<string, string>();
  for (const edge of edges) {
    if (hostIds.has(edge.target) && !hostIds.has(edge.source) && !parents.has(edge.target)) {
      parents.set(edge.target, edge.source);
    }
    if (hostIds.has(edge.source) && !hostIds.has(edge.target) && !parents.has(edge.source)) {
      parents.set(edge.source, edge.target);
    }
  }
  return parents;
};

const dedupeEdges = (edges: readonly TopologyEdge[]): readonly TopologyEdge[] => {
  const seen = new Set<string>();
  const unique: TopologyEdge[] = [];
  for (const edge of edges) {
    const key = [edge.source, edge.target].sort().join("|");
    if (!seen.has(key)) {
      seen.add(key);
      unique.push(edge);
    }
  }
  return unique;
};

export const layoutTopology = (
  topology: Topology,
  { width, height }: { readonly width: number; readonly height: number },
): TopologyLayout => {
  const nodes = [...topology.nodes].sort(compareNodes);
  const edges = [...topology.edges].sort(compareEdges);
  const switches = nodes.filter((node) => node.kind === "switch");
  const hosts = nodes.filter((node) => node.kind === "host");
  const depths = switchDepths(switches, edges);
  const parents = hostParents(hosts, edges);
  const layerCount = switches.length === 0 ? 0 : Math.max(...switches.map((node) => depths.get(node.id) ?? 0)) + 1;
  const rows = layerCount + (hosts.length > 0 ? 1 : 0);

  const positioned = new Map<string, PositionedNode>();
  for (let depth = 0; depth < layerCount; depth += 1) {
    const layer = switches.filter((node) => (depths.get(node.id) ?? 0) === depth);
    layer.forEach((node, index) => {
      positioned.set(node.id, { ...node, depth, x: spread(index, layer.length, width), y: rowY(depth, rows, height) });
    });
  }

  const hostOrder = [...hosts].sort((left, right) => {
    const leftParent = positioned.get(parents.get(left.id) ?? "");
    const rightParent = positioned.get(parents.get(right.id) ?? "");
    return (
      (leftParent?.x ?? Number.POSITIVE_INFINITY) - (rightParent?.x ?? Number.POSITIVE_INFINITY) ||
      compareNodes(left, right)
    );
  });
  hostOrder.forEach((node, index) => {
    positioned.set(node.id, {
      ...node,
      depth: layerCount,
      x: spread(index, hostOrder.length, width),
      y: rowY(rows - 1, rows, height),
    });
  });

  const positionedEdges = dedupeEdges(edges).flatMap((edge): PositionedEdge[] => {
    const source = positioned.get(edge.source);
    const target = positioned.get(edge.target);
    if (source === undefined || target === undefined) {
      return [];
    }
    return [{ ...edge, x1: source.x, y1: source.y, x2: target.x, y2: target.y }];
  });

  return { width, height, nodes: nodes.flatMap((node) => positioned.get(node.id) ?? []), edges: positionedEdges };
};

export const utilizationLevel = (utilization: number | null): UtilizationLevel => {
  if (utilization === null) {
    return "unknown";
  }
  if (utilization <= 0) {
    return "idle";
  }
  if (utilization < 0.3) {
    return "low";
  }
  if (utilization < 0.7) {
    return "medium";
  }
  if (utilization < 0.9) {
    return "high";
  }
  return "saturated";
};

export const utilizationByPort = (snapshot: KpiSnapshot | null): ReadonlyMap<PortKey, number | null> => {
  const lookup = new Map<PortKey, number | null>();
  for (const switchKpis of snapshot?.switches ?? []) {
    for (const port of switchKpis.ports) {
      lookup.set(portKey(port.dpid, port.port_no), port.utilization);
    }
  }
  return lookup;
};

const parseDpid = (nodeId: string): number | null => {
  const [kind, dpid] = nodeId.split(":");
  if (kind !== "switch" && kind !== "s") {
    return null;
  }
  const parsed = Number(dpid);
  return Number.isInteger(parsed) ? parsed : null;
};

const portUtilization = (
  nodeId: string,
  portNo: number | null,
  lookup: ReadonlyMap<PortKey, number | null>,
): number | null => {
  const dpid = parseDpid(nodeId);
  if (dpid === null || portNo === null) {
    return null;
  }
  return lookup.get(portKey(dpid, portNo)) ?? null;
};

export const edgeUtilization = (edge: TopologyEdge, lookup: ReadonlyMap<PortKey, number | null>): number | null => {
  const candidates = [
    portUtilization(edge.source, edge.source_port, lookup),
    portUtilization(edge.target, edge.target_port, lookup),
  ].filter((value): value is number => value !== null);
  return candidates.length === 0 ? null : Math.max(...candidates);
};
