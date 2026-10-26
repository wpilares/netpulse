import { type PointerEvent, useState } from "react";
import { formatClock } from "../../lib/time";
import type { PortKpis } from "../telemetry/frames";
import { type ChartFrame, formatBps, linePath, niceMax, seriesOf, type ThroughputField } from "./chart";

const WIDTH = 320;
const HEIGHT = 160;
const MARGIN = { top: 12, right: 12, bottom: 22, left: 60 } as const;
const PLOT = { width: WIDTH - MARGIN.left - MARGIN.right, height: HEIGHT - MARGIN.top - MARGIN.bottom } as const;
const SERIES: readonly { readonly field: ThroughputField; readonly key: "rx" | "tx"; readonly label: string }[] = [
  { field: "rx_bps", key: "rx", label: "Receive" },
  { field: "tx_bps", key: "tx", label: "Transmit" },
];

export interface PortChartProps {
  readonly portNo: number;
  readonly points: readonly PortKpis[];
}

const maxThroughput = (points: readonly PortKpis[]): number =>
  Math.max(0, ...points.flatMap((point) => [point.rx_bps ?? 0, point.tx_bps ?? 0]));

const nearestIndex = (ratio: number, count: number): number =>
  Math.min(count - 1, Math.max(0, Math.round(ratio * (count - 1))));

export const PortChart = ({ portNo, points }: PortChartProps) => {
  const [hovered, setHovered] = useState<number | null>(null);
  const first = points[0];
  const last = points[points.length - 1];
  const label = `Port ${portNo} throughput, ${points.length} ${points.length === 1 ? "sample" : "samples"}`;
  const yMax = niceMax(maxThroughput(points));
  const frame: ChartFrame = {
    width: PLOT.width,
    height: PLOT.height,
    xDomain: [Date.parse(first?.computed_at ?? ""), Date.parse(last?.computed_at ?? "")],
    yDomain: [0, yMax],
  };
  const focused = hovered === null ? last : (points[hovered] ?? last);

  const onPointerMove = (event: PointerEvent<SVGRectElement>) => {
    const bounds = event.currentTarget.getBoundingClientRect();
    if (bounds.width === 0 || points.length === 0) {
      return;
    }
    setHovered(nearestIndex((event.clientX - bounds.left) / bounds.width, points.length));
  };

  return (
    <figure className="chart">
      <svg
        className="chart__canvas"
        role="img"
        aria-label={label}
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        preserveAspectRatio="xMidYMid meet"
      >
        <title>{label}</title>
        <g transform={`translate(${MARGIN.left} ${MARGIN.top})`}>
          {[0, 0.5, 1].map((fraction) => {
            const y = PLOT.height - fraction * PLOT.height;
            return (
              <g key={fraction} className="chart__tick">
                <line x1={0} x2={PLOT.width} y1={y} y2={y} />
                {points.length === 0 ? null : (
                  <text x={-8} y={y} textAnchor="end" dominantBaseline="central">
                    {formatBps(fraction * yMax)}
                  </text>
                )}
              </g>
            );
          })}
          {points.length === 0 ? (
            <text className="chart__empty" x={PLOT.width / 2} y={PLOT.height / 2} textAnchor="middle">
              Waiting for samples
            </text>
          ) : (
            SERIES.map((series) => (
              <path
                key={series.key}
                className="chart__line"
                data-series={series.key}
                d={linePath(seriesOf(points, series.field), frame)}
              />
            ))
          )}
          {hovered !== null && focused !== undefined ? (
            <line
              className="chart__cursor"
              x1={(hovered / Math.max(1, points.length - 1)) * PLOT.width}
              x2={(hovered / Math.max(1, points.length - 1)) * PLOT.width}
              y1={0}
              y2={PLOT.height}
            />
          ) : null}
          {first !== undefined && last !== undefined ? (
            <g className="chart__axis">
              <text x={0} y={PLOT.height + 16}>
                {formatClock(first.computed_at)}
              </text>
              <text x={PLOT.width} y={PLOT.height + 16} textAnchor="end">
                {formatClock(last.computed_at)}
              </text>
            </g>
          ) : null}
          <rect
            className="chart__hit"
            width={PLOT.width}
            height={PLOT.height}
            onPointerMove={onPointerMove}
            onPointerLeave={() => setHovered(null)}
          />
        </g>
      </svg>
      <figcaption className="chart__legend">
        {SERIES.map((series) => (
          <span key={series.key} className="chart__legend-item" data-series={series.key}>
            <span className="chart__swatch" aria-hidden="true" />
            <span>{series.label}</span>
            <strong>{formatBps(focused?.[series.field] ?? null)}</strong>
          </span>
        ))}
        {focused !== undefined ? <span className="chart__legend-time">{formatClock(focused.computed_at)}</span> : null}
      </figcaption>
    </figure>
  );
};
