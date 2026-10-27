import type { LucideIcon } from "lucide-react";
import { cx } from "./cx";
import styles from "./Icon.module.css";

export type IconGlyph = LucideIcon;
export type IconSize = "sm" | "md" | "lg";

const pixelSizes: Record<IconSize, number> = { sm: 14, md: 16, lg: 20 };

export interface IconProps {
  readonly icon: IconGlyph;
  readonly size?: IconSize;
  readonly label?: string;
  readonly className?: string | undefined;
}

export const Icon = ({ icon: Glyph, size = "md", label, className }: IconProps) => (
  <Glyph
    size={pixelSizes[size]}
    strokeWidth={2}
    focusable="false"
    className={cx(styles.icon, className)}
    {...(label === undefined ? { "aria-hidden": true } : { role: "img", "aria-label": label })}
  />
);
