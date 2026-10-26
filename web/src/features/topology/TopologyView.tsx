import { formatRate } from "../kpis/chart";
import type { KpiSnapshot } from "../telemetry/frames";
import {
  edgeUtilization,
  layoutTopology,
  type PositionedNode,
  type TopologyState,
  utilizationByPort,
  utilizationLevel,
} from "./topology";

const VIEW = { width: 800, height: 360 } as const;
const SWITCH_SIZE = { width: 56, height: 32 } as const;
const HOST_RADIUS = 10;

export interface TopologyViewProps {
  readonly state: TopologyState;
  readonly latest: KpiSnapshot | null;
}

const plural = (count: number, noun: string): string => `${count} ${noun}${count === 1 ? "" : "es"}`;

const describe = (switches: number, hosts: number): string =>
  `Network topology: ${plural(switches, "switch")}, ${hosts} ${hosts === 1 ? "host" : "hosts"}`;

const SwitchNode = ({ node }: { readonly node: PositionedNode }) => (
  <g className="topology__node" data-kind="switch" transform={`translate(${node.x} ${node.y})`}>
    <rect
      className="topology__switch"
      x={-SWITCH_SIZE.width / 2}
      y={-SWITCH_SIZE.height / 2}
      width={SWITCH_SIZE.width}
      height={SWITCH_SIZE.height}
      rx={6}
    />
    <text className="topology__label" textAnchor="middle" dominantBaseline="central">
      {node.label}
    </text>
  </g>
);

const HostNode = ({ node }: { readonly node: PositionedNode }) => (
  <g className="topology__node" data-kind="host" transform={`translate(${node.x} ${node.y})`}>
    <circle className="topology__host" r={HOST_RADIUS} />
    <text className="topology__label" textAnchor="middle" y={HOST_RADIUS + 14}>
      {node.label}
    </text>
  </g>
);

export const TopologyView = ({ state, latest }: TopologyViewProps) => {
  if (state.kind === "loading") {
    return <p className="topology__notice">Loading topology…</p>;
  }
  if (state.kind === "unavailable") {
    return <p className="topology__notice">Topology unavailable: controller unreachable.</p>;
  }

  const layout = layoutTopology(state.topology, VIEW);
  const utilization = utilizationByPort(latest);
  const switches = layout.nodes.filter((node) => node.kind === "switch").length;
  const hosts = layout.nodes.length - switches;
  const label = describe(switches, hosts);

  return (
    <svg
      className="topology"
      role="img"
      aria-label={label}
      viewBox={`0 0 ${VIEW.width} ${VIEW.height}`}
      preserveAspectRatio="xMidYMid meet"
    >
      <title>{label}</title>
      <g className="topology__edges">
        {layout.edges.map((edge) => {
          const value = edgeUtilization(edge, utilization);
          return (
            <line
              key={`${edge.source}|${edge.target}`}
              className="topology__edge"
              data-level={utilizationLevel(value)}
              x1={edge.x1}
              y1={edge.y1}
              x2={edge.x2}
              y2={edge.y2}
            >
              <title>{`${edge.source} to ${edge.target}: utilization ${formatRate(value)}`}</title>
            </line>
          );
        })}
      </g>
      <g className="topology__nodes">
        {layout.nodes.map((node) =>
          node.kind === "switch" ? <SwitchNode key={node.id} node={node} /> : <HostNode key={node.id} node={node} />,
        )}
      </g>
    </svg>
  );
};
