import type { ComponentProps } from "react";
import { cx } from "./cx";
import styles from "./Switch.module.css";
import { VisuallyHidden } from "./VisuallyHidden";

export interface SwitchProps extends Omit<ComponentProps<"button">, "onChange" | "children" | "type" | "role"> {
  readonly checked: boolean;
  readonly label: string;
  readonly onChange: (checked: boolean) => void;
  readonly hideLabel?: boolean;
}

export const Switch = ({ checked, label, onChange, hideLabel = false, className, ...rest }: SwitchProps) => (
  <button
    type="button"
    role="switch"
    aria-checked={checked}
    className={cx(styles.switch, className)}
    onClick={() => onChange(!checked)}
    {...rest}
  >
    <span className={styles.track} aria-hidden="true">
      <span className={styles.thumb} />
    </span>
    {hideLabel ? <VisuallyHidden>{label}</VisuallyHidden> : <span className={styles.label}>{label}</span>}
  </button>
);
