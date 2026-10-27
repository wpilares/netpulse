import type { ReactNode } from "react";
import { cx } from "./cx";
import styles from "./EmptyState.module.css";
import { Icon, type IconGlyph } from "./Icon";

export interface EmptyStateProps {
  readonly title: string;
  readonly description?: string;
  readonly icon?: IconGlyph;
  readonly action?: ReactNode;
  readonly className?: string;
}

export const EmptyState = ({ title, description, icon, action, className }: EmptyStateProps) => (
  <div className={cx(styles.empty, className)}>
    {icon === undefined ? null : (
      <span className={styles.icon}>
        <Icon icon={icon} size="lg" />
      </span>
    )}
    <p className={styles.title}>{title}</p>
    {description === undefined ? null : <p className={styles.description}>{description}</p>}
    {action === undefined ? null : <div className={styles.action}>{action}</div>}
  </div>
);
