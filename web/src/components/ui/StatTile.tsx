import type { ReactNode } from "react";
import type { Tone } from "../tone";
import { cx } from "./cx";
import styles from "./StatTile.module.css";

export interface StatTileProps {
  readonly label: string;
  readonly value: ReactNode;
  readonly hint?: string;
  readonly tone?: Tone;
  readonly className?: string;
}

export const StatTile = ({ label, value, hint, tone = "neutral", className }: StatTileProps) => (
  <div className={cx(styles.tile, className)} data-tone={tone}>
    <span className={styles.label}>{label}</span>
    <span className={styles.value}>{value}</span>
    {hint === undefined ? null : <span className={styles.hint}>{hint}</span>}
  </div>
);
