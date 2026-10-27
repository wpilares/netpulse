import type { ReactNode } from "react";
import styles from "./ChartFrame.module.css";
import { cx } from "./cx";

export interface ChartSeries {
  readonly id: string;
  readonly label: string;
  readonly value: string;
  readonly color: string;
}

export interface ChartFrameProps {
  readonly title: string;
  readonly series: readonly ChartSeries[];
  readonly caption?: string;
  readonly className?: string;
  readonly children: ReactNode;
}

export const ChartFrame = ({ title, series, caption, className, children }: ChartFrameProps) => (
  <figure className={cx(styles.frame, className)}>
    <div className={styles.header}>
      <span className={styles.title}>{title}</span>
      {caption === undefined ? null : <span className={styles.caption}>{caption}</span>}
    </div>
    <div className={styles.plot}>{children}</div>
    <figcaption className={styles.legend}>
      <ul className={styles.series} aria-label={`${title} series`}>
        {series.map((entry) => (
          <li key={entry.id} className={styles.item} data-series={entry.id}>
            <span className={styles.swatch} style={{ background: entry.color }} aria-hidden="true" />
            <span className={styles.label}>{entry.label}</span>
            <strong className={styles.value}>{entry.value}</strong>
          </li>
        ))}
      </ul>
    </figcaption>
  </figure>
);
