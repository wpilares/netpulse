import { LoaderCircle } from "lucide-react";
import type { ComponentProps, ReactNode } from "react";
import styles from "./Button.module.css";
import { cx } from "./cx";
import { Icon } from "./Icon";

export type ButtonVariant = "primary" | "secondary" | "ghost";
export type ButtonSize = "sm" | "md";

export interface ButtonProps extends ComponentProps<"button"> {
  readonly variant?: ButtonVariant;
  readonly size?: ButtonSize;
  readonly loading?: boolean;
  readonly icon?: ReactNode;
}

export const Button = ({
  variant = "secondary",
  size = "md",
  loading = false,
  icon,
  type = "button",
  disabled = false,
  className,
  children,
  ...rest
}: ButtonProps) => (
  <button
    type={type}
    className={cx(styles.button, styles[variant], styles[size], className)}
    data-variant={variant}
    data-size={size}
    disabled={disabled || loading}
    {...(loading ? { "aria-busy": true } : {})}
    {...rest}
  >
    {loading ? (
      <Icon icon={LoaderCircle} size={size === "sm" ? "sm" : "md"} className={styles.spinner} />
    ) : icon === undefined ? null : (
      <span className={styles.icon}>{icon}</span>
    )}
    {children === undefined || children === null ? null : <span className={styles.label}>{children}</span>}
  </button>
);
