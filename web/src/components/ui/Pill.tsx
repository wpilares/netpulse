import type { HTMLAttributes } from "react";
import type { Tone } from "../tone";
import { cx } from "./cx";
import styles from "./Pill.module.css";

export type PillElement = "span" | "output";

export interface PillProps extends Omit<HTMLAttributes<HTMLElement>, "children"> {
  readonly tone: Tone;
  readonly label: string;
  readonly detail?: string | null;
  readonly pulse?: boolean;
  readonly as?: PillElement;
}

export const Pill = ({
  tone,
  label,
  detail = null,
  pulse = false,
  as: Element = "span",
  className,
  ...rest
}: PillProps) => (
  <Element className={cx(styles.pill, className)} data-tone={tone} {...(pulse ? { "data-pulse": true } : {})} {...rest}>
    <span className={styles.dot} aria-hidden="true" />
    <span className={styles.label}>{label}</span>
    {detail === null ? null : <span className={styles.detail}>{detail}</span>}
  </Element>
);
