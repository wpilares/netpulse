import { Skeleton, StatTile, VisuallyHidden } from "../../components/ui";
import type { NetworkSummary } from "../telemetry/frames";
import styles from "./SummaryGrid.module.css";
import { SUMMARY_TILE_COUNT, summaryTiles } from "./summary";

export interface SummaryGridProps {
  readonly summary: NetworkSummary;
}

export const SummaryGrid = ({ summary }: SummaryGridProps) => (
  <div className={styles.grid}>
    {summaryTiles(summary).map((tile) => (
      <StatTile key={tile.id} label={tile.label} value={tile.value} tone={tile.tone} />
    ))}
  </div>
);

const placeholders = Array.from({ length: SUMMARY_TILE_COUNT }, (_, index) => index);

export const SummarySkeleton = () => (
  <div className={styles.grid} aria-busy="true">
    <VisuallyHidden>Loading network summary</VisuallyHidden>
    {placeholders.map((index) => (
      <Skeleton key={index} height="4.5rem" />
    ))}
  </div>
);
