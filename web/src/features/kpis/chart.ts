import type { PortKpis } from "../telemetry/frames";

export interface ChartPoint {
  readonly x: number;
  readonly y: number | null;
}

export interface ChartFrame {
  readonly width: number;
  readonly height: number;
  readonly xDomain: readonly [number, number];
  readonly yDomain: readonly [number, number];
}

export type ThroughputField = "rx_bps" | "tx_bps";

const PLACEHOLDER = "—";

const scale = (value: number, [min, max]: readonly [number, number], size: number): number => {
  const span = max - min;
  return span === 0 ? 0 : ((value - min) / span) * size;
};

const round = (value: number): string => String(Math.round(value * 100) / 100);

export const linePath = (points: readonly ChartPoint[], frame: ChartFrame): string => {
  let path = "";
  let drawing = false;
  for (const point of points) {
    if (point.y === null) {
      drawing = false;
      continue;
    }
    const x = round(scale(point.x, frame.xDomain, frame.width));
    const y = round(frame.height - scale(point.y, frame.yDomain, frame.height));
    path += `${drawing ? "L" : "M"}${x} ${y}`;
    drawing = true;
  }
  return path;
};

export const niceMax = (value: number): number => {
  if (!(value > 0)) {
    return 1;
  }
  const magnitude = 10 ** Math.floor(Math.log10(value));
  const fraction = value / magnitude;
  const step = fraction <= 1 ? 1 : fraction <= 2 ? 2 : fraction <= 5 ? 5 : 10;
  return step * magnitude;
};

const scaled = (value: number, unit: number): string => (value / unit).toFixed(1);

export const formatBps = (value: number | null): string => {
  if (value === null) {
    return PLACEHOLDER;
  }
  if (value >= 1e9) {
    return `${scaled(value, 1e9)} Gb/s`;
  }
  if (value >= 1e6) {
    return `${scaled(value, 1e6)} Mb/s`;
  }
  if (value >= 1e3) {
    return `${scaled(value, 1e3)} kb/s`;
  }
  return `${Math.round(value)} b/s`;
};

export const formatRate = (ratio: number | null): string =>
  ratio === null ? PLACEHOLDER : `${(ratio * 100).toFixed(1)}%`;

export const formatPps = (value: number | null): string => {
  if (value === null) {
    return PLACEHOLDER;
  }
  return value >= 1e3 ? `${scaled(value, 1e3)} kpps` : `${Math.round(value)} pps`;
};

export const formatCount = (value: number | null): string => (value === null ? PLACEHOLDER : String(value));

export const seriesOf = (points: readonly PortKpis[], field: ThroughputField): readonly ChartPoint[] =>
  points.map((point) => ({ x: Date.parse(point.computed_at), y: point[field] }));
