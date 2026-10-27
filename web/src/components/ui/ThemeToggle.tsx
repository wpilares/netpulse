import { Monitor, Moon, Sun } from "lucide-react";
import { useTheme } from "../../theme/ThemeProvider";
import type { ThemePreference } from "../../theme/theme";
import { Icon } from "./Icon";
import { SegmentedControl, type SegmentedOption } from "./SegmentedControl";

const options: readonly SegmentedOption<ThemePreference>[] = [
  { value: "light", label: "Light", icon: <Icon icon={Sun} size="sm" /> },
  { value: "dark", label: "Dark", icon: <Icon icon={Moon} size="sm" /> },
  { value: "system", label: "System", icon: <Icon icon={Monitor} size="sm" /> },
];

export interface ThemeToggleProps {
  readonly compact?: boolean;
  readonly className?: string;
}

export const ThemeToggle = ({ compact = false, className }: ThemeToggleProps) => {
  const { preference, setPreference } = useTheme();
  return (
    <SegmentedControl
      label="Theme"
      options={options}
      value={preference}
      onChange={setPreference}
      size="sm"
      hideLabels={compact}
      {...(className === undefined ? {} : { className })}
    />
  );
};
