import type { Tone } from "../tone";
import { Pill } from "./Pill";

export interface StatusPillProps {
  readonly tone: Tone;
  readonly label: string;
  readonly detail?: string | null;
  readonly pulse?: boolean;
  readonly className?: string;
}

export const StatusPill = ({ tone, label, detail = null, pulse = false, className }: StatusPillProps) => (
  <Pill
    as="output"
    aria-live="polite"
    tone={tone}
    label={label}
    detail={detail}
    pulse={pulse}
    {...(className === undefined ? {} : { className })}
  />
);
