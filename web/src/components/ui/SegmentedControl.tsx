import { type KeyboardEvent, type ReactNode, useId, useRef } from "react";
import { cx } from "./cx";
import styles from "./SegmentedControl.module.css";
import { VisuallyHidden } from "./VisuallyHidden";

export interface SegmentedOption<T extends string> {
  readonly value: T;
  readonly label: string;
  readonly icon?: ReactNode;
}

export type SegmentedSize = "sm" | "md";

export interface SegmentedControlProps<T extends string> {
  readonly label: string;
  readonly options: readonly SegmentedOption<T>[];
  readonly value: T;
  readonly onChange: (value: T) => void;
  readonly size?: SegmentedSize;
  readonly hideLabels?: boolean;
  readonly className?: string;
}

const steps: Readonly<Record<string, number>> = {
  ArrowRight: 1,
  ArrowDown: 1,
  ArrowLeft: -1,
  ArrowUp: -1,
};

export const nextOptionValue = <T extends string>(
  options: readonly SegmentedOption<T>[],
  current: T,
  key: string,
): T | null => {
  const first = options[0];
  const last = options[options.length - 1];
  if (first === undefined || last === undefined) {
    return null;
  }
  if (key === "Home") {
    return first.value;
  }
  if (key === "End") {
    return last.value;
  }
  const step = steps[key];
  if (step === undefined) {
    return null;
  }
  const index = options.findIndex((option) => option.value === current);
  const next = options[(index + step + options.length) % options.length];
  return next === undefined ? null : next.value;
};

export const SegmentedControl = <T extends string>({
  label,
  options,
  value,
  onChange,
  size = "md",
  hideLabels = false,
  className,
}: SegmentedControlProps<T>) => {
  const name = useId();
  const inputs = useRef(new Map<T, HTMLInputElement>());

  const handleKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    const next = nextOptionValue(options, value, event.key);
    if (next === null) {
      return;
    }
    event.preventDefault();
    onChange(next);
    inputs.current.get(next)?.focus();
  };

  return (
    <div role="radiogroup" aria-label={label} className={cx(styles.group, styles[size], className)} data-size={size}>
      {options.map((option) => {
        const selected = option.value === value;
        return (
          <label key={option.value} className={styles.option} data-selected={selected}>
            <input
              type="radio"
              name={name}
              value={option.value}
              checked={selected}
              tabIndex={selected ? 0 : -1}
              className={styles.input}
              onChange={() => onChange(option.value)}
              onKeyDown={handleKeyDown}
              ref={(node) => {
                if (node === null) {
                  inputs.current.delete(option.value);
                } else {
                  inputs.current.set(option.value, node);
                }
              }}
            />
            {option.icon === undefined ? null : <span className={styles.icon}>{option.icon}</span>}
            {hideLabels ? (
              <VisuallyHidden>{option.label}</VisuallyHidden>
            ) : (
              <span className={styles.label}>{option.label}</span>
            )}
          </label>
        );
      })}
    </div>
  );
};
