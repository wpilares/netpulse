import type { ComponentProps } from "react";
import { cx } from "./cx";

export type VisuallyHiddenProps = ComponentProps<"span">;

export const VisuallyHidden = ({ className, ...rest }: VisuallyHiddenProps) => (
  <span className={cx("sr-only", className)} {...rest} />
);
