import { cx } from "./cx";
import styles from "./Skeleton.module.css";

export type SkeletonRounded = "sm" | "md" | "full";

export interface SkeletonProps {
  readonly width?: number | string;
  readonly height?: number | string;
  readonly rounded?: SkeletonRounded;
  readonly className?: string;
}

export const Skeleton = ({ width = "100%", height = "1em", rounded = "md", className }: SkeletonProps) => (
  <span
    className={cx(styles.skeleton, className)}
    data-rounded={rounded}
    style={{ width, height }}
    aria-hidden="true"
  />
);
