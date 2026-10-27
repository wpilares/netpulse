import { RefreshCw, TriangleAlert } from "lucide-react";
import { Button } from "./Button";
import { cx } from "./cx";
import styles from "./ErrorState.module.css";
import { Icon } from "./Icon";

export interface ErrorStateProps {
  readonly title?: string;
  readonly description?: string;
  readonly onRetry?: () => void;
  readonly retryLabel?: string;
  readonly className?: string;
}

export const ErrorState = ({
  title = "Something went wrong",
  description,
  onRetry,
  retryLabel = "Retry",
  className,
}: ErrorStateProps) => (
  <div role="alert" className={cx(styles.error, className)} data-tone="critical">
    <span className={styles.icon}>
      <Icon icon={TriangleAlert} size="lg" />
    </span>
    <div className={styles.text}>
      <p className={styles.title}>{title}</p>
      {description === undefined ? null : <p className={styles.description}>{description}</p>}
    </div>
    {onRetry === undefined ? null : (
      <Button size="sm" onClick={onRetry} icon={<Icon icon={RefreshCw} size="sm" />}>
        {retryLabel}
      </Button>
    )}
  </div>
);
