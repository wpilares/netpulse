import { fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";
import { nextOptionValue, SegmentedControl, type SegmentedOption } from "./SegmentedControl";

type Mode = "light" | "dark" | "system";

const options: readonly SegmentedOption<Mode>[] = [
  { value: "light", label: "Light" },
  { value: "dark", label: "Dark" },
  { value: "system", label: "System" },
];

const Harness = ({ initial, onChange }: { readonly initial: Mode; readonly onChange: (value: Mode) => void }) => {
  const [value, setValue] = useState<Mode>(initial);
  return (
    <SegmentedControl
      label="Theme"
      options={options}
      value={value}
      onChange={(next) => {
        setValue(next);
        onChange(next);
      }}
    />
  );
};

describe("nextOptionValue", () => {
  it("moves forward and backward with wrap-around", () => {
    expect(nextOptionValue(options, "light", "ArrowRight")).toBe("dark");
    expect(nextOptionValue(options, "system", "ArrowDown")).toBe("light");
    expect(nextOptionValue(options, "light", "ArrowLeft")).toBe("system");
    expect(nextOptionValue(options, "dark", "ArrowUp")).toBe("light");
  });

  it("jumps to the ends and ignores other keys", () => {
    expect(nextOptionValue(options, "dark", "Home")).toBe("light");
    expect(nextOptionValue(options, "dark", "End")).toBe("system");
    expect(nextOptionValue(options, "dark", "Enter")).toBeNull();
  });
});

describe("SegmentedControl", () => {
  it("renders a labelled radiogroup with the selected option checked", () => {
    render(<Harness initial="dark" onChange={vi.fn()} />);

    expect(screen.getByRole("radiogroup", { name: "Theme" })).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: "Dark" })).toBeChecked();
    expect(screen.getByRole("radio", { name: "Light" })).not.toBeChecked();
    expect(screen.getByRole("radio", { name: "Dark" })).toHaveAttribute("tabindex", "0");
    expect(screen.getByRole("radio", { name: "Light" })).toHaveAttribute("tabindex", "-1");
  });

  it("selects an option on click", () => {
    const onChange = vi.fn();
    render(<Harness initial="light" onChange={onChange} />);

    fireEvent.click(screen.getByRole("radio", { name: "System" }));

    expect(onChange).toHaveBeenCalledWith("system");
    expect(screen.getByRole("radio", { name: "System" })).toBeChecked();
  });

  it("moves the selection and focus with arrow keys, wrapping around", () => {
    const onChange = vi.fn();
    render(<Harness initial="dark" onChange={onChange} />);
    const dark = screen.getByRole("radio", { name: "Dark" });
    dark.focus();

    fireEvent.keyDown(dark, { key: "ArrowRight" });

    expect(onChange).toHaveBeenLastCalledWith("system");
    const system = screen.getByRole("radio", { name: "System" });
    expect(system).toBeChecked();
    expect(system).toHaveFocus();

    fireEvent.keyDown(system, { key: "ArrowRight" });

    expect(onChange).toHaveBeenLastCalledWith("light");
    expect(screen.getByRole("radio", { name: "Light" })).toHaveFocus();
  });

  it("jumps to the first and last option with Home and End", () => {
    const onChange = vi.fn();
    render(<Harness initial="dark" onChange={onChange} />);

    fireEvent.keyDown(screen.getByRole("radio", { name: "Dark" }), { key: "End" });
    expect(onChange).toHaveBeenLastCalledWith("system");

    fireEvent.keyDown(screen.getByRole("radio", { name: "System" }), { key: "Home" });
    expect(onChange).toHaveBeenLastCalledWith("light");
  });

  it("keeps an accessible name when labels are visually hidden", () => {
    render(<SegmentedControl label="Theme" options={options} value="light" onChange={vi.fn()} hideLabels />);

    expect(screen.getByRole("radio", { name: "Dark" })).toBeInTheDocument();
  });
});
