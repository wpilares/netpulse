import type { ComponentProps, ReactNode } from "react";
import styles from "./Card.module.css";
import { cx } from "./cx";

export type CardProps = ComponentProps<"section">;

export const Card = ({ className, ...rest }: CardProps) => <section className={cx(styles.card, className)} {...rest} />;

export interface CardHeaderProps extends ComponentProps<"div"> {
  readonly actions?: ReactNode;
}

export const CardHeader = ({ actions, className, children, ...rest }: CardHeaderProps) => (
  <div className={cx(styles.header, className)} {...rest}>
    <div className={styles.heading}>{children}</div>
    {actions === undefined ? null : <div className={styles.actions}>{actions}</div>}
  </div>
);

export type CardTitleLevel = 2 | 3;

export interface CardTitleProps extends ComponentProps<"h2"> {
  readonly level?: CardTitleLevel;
}

export const CardTitle = ({ level = 2, className, ...rest }: CardTitleProps) => {
  const Heading = level === 3 ? "h3" : "h2";
  return <Heading className={cx(styles.title, className)} {...rest} />;
};

export type CardBodyProps = ComponentProps<"div">;

export const CardBody = ({ className, ...rest }: CardBodyProps) => (
  <div className={cx(styles.body, className)} {...rest} />
);
