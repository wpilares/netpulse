import type { ComponentProps } from "react";
import type { Tone } from "../tone";
import styles from "./Badge.module.css";
import { cx } from "./cx";

export type BadgeVariant = "solid" | "soft";

export interface BadgeProps extends ComponentProps<"span"> {
  readonly tone?: Tone;
  readonly variant?: BadgeVariant;
}

export const Badge = ({ tone = "neutral", variant = "soft", className, ...rest }: BadgeProps) => (
  <span className={cx(styles.badge, styles[variant], className)} data-tone={tone} data-variant={variant} {...rest} />
);
