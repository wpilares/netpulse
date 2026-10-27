import {
  Badge,
  Card,
  CardBody,
  CardHeader,
  CardTitle,
  ErrorState,
  Skeleton,
  VisuallyHidden,
} from "../../components/ui";
import { formatRate } from "../kpis/chart";
import type { KpiSnapshot } from "../telemetry/frames";
import styles from "./TopologyView.module.css";
import {
  edgeUtilization,
  layoutTopology,
  type PositionedNode,
  type TopologyState,
  UTILIZATION_LEGEND,
  utilizationByPort,
  utilizationLevel,
} from "./topology";

const HEADING_ID = "topology-heading";
const VIEW = { width: 800, height: 360 } as const;
const SWITCH_SIZE = { width: 56, height: 32 } as const;
const HOST_RADIUS = 10;

export interface TopologyViewProps {
  readonly state: TopologyState;
  readonly latest: KpiSnapshot | null;
  readonly onRetry?: () => void;
}

const plural = (count: number, noun: string): string => `${count} ${noun}${count === 1 ? "" : "es"}`;

const describe = (switches: number, hosts: number): string =>
  `Network topology: ${plural(switches, "switch")}, ${hosts} ${hosts === 1 ? "host" : "hosts"}`;

const SwitchNode = ({ node }: { readonly node: PositionedNode }) => (
  <g data-kind="switch" transform={`translate(${node.x} ${node.y})`}>
    <rect
      className={styles.switch}
      x={-SWITCH_SIZE.width / 2}
      y={-SWITCH_SIZE.height / 2}
      width={SWITCH_SIZE.width}
      height={SWITCH_SIZE.height}
      rx={6}
    />
    <text className={styles.label} textAnchor="middle" dominantBaseline="central">
      {node.label}
    </text>
  </g>
);

const HostNode = ({ node }: { readonly node: PositionedNode }) => (
  <g data-kind="host" transform={`translate(${node.x} ${node.y})`}>
    <circle className={styles.host} r={HOST_RADIUS} />
    <text className={styles.label} textAnchor="middle" y={HOST_RADIUS + 14}>
      {node.label}
    </text>
  </g>
);

const Legend = () => (
  <ul className={styles.legend} aria-label="Utilization levels">
    {UTILIZATION_LEGEND.map((entry) => (
      <li key={entry.level}>
        <Badge tone="neutral">
          <span className={styles.swatch} data-level={entry.level} aria-hidden="true" />
          {entry.label}
        </Badge>
      </li>
    ))}
  </ul>
);

const Graph = ({ state, latest }: { readonly state: TopologyState; readonly latest: KpiSnapshot | null }) => {
  if (state.kind !== "ready") {
    return null;
  }
  const layout = layoutTopology(state.topology, VIEW);
  const utilization = utilizationByPort(latest);
  const switches = layout.nodes.filter((node) => node.kind === "switch").length;
  const hosts = layout.nodes.length - switches;
  const label = describe(switches, hosts);

  return (
    <svg
      className={styles.graph}
      role="img"
      aria-label={label}
      viewBox={`0 0 ${VIEW.width} ${VIEW.height}`}
      preserveAspectRatio="xMidYMid meet"
    >
      <title>{label}</title>
      <g>
        {layout.edges.map((edge) => {
          const value = edgeUtilization(edge, utilization);
          return (
            <line
              key={`${edge.source}|${edge.target}`}
              className={styles.edge}
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
      <g>
        {layout.nodes.map((node) =>
          node.kind === "switch" ? <SwitchNode key={node.id} node={node} /> : <HostNode key={node.id} node={node} />,
        )}
      </g>
    </svg>
  );
};

const Body = ({ state, latest, onRetry }: TopologyViewProps) => {
  switch (state.kind) {
    case "loading":
      return (
        <div aria-busy="true">
          <VisuallyHidden>Loading topology…</VisuallyHidden>
          <Skeleton height="14rem" />
        </div>
      );
    case "unavailable":
      return (
        <ErrorState
          title="Topology unavailable"
          description="Controller unreachable."
          {...(onRetry === undefined ? {} : { onRetry })}
        />
      );
    case "ready":
      return <Graph state={state} latest={latest} />;
  }
};

export const TopologyView = ({ state, latest, onRetry }: TopologyViewProps) => (
  <Card aria-labelledby={HEADING_ID}>
    <CardHeader actions={<Legend />}>
      <CardTitle id={HEADING_ID}>Topology</CardTitle>
    </CardHeader>
    <CardBody>
      <Body state={state} latest={latest} {...(onRetry === undefined ? {} : { onRetry })} />
    </CardBody>
  </Card>
);
