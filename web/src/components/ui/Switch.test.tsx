import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { Switch } from "./Switch";

describe("Switch", () => {
  it("renders a labelled switch reflecting its checked state", () => {
    render(<Switch checked label="Show resolved" onChange={vi.fn()} />);

    const control = screen.getByRole("switch", { name: "Show resolved" });
    expect(control).toHaveAttribute("aria-checked", "true");
  });

  it("reports the toggled value on click", () => {
    const onChange = vi.fn();
    const { rerender } = render(<Switch checked={false} label="Show resolved" onChange={onChange} />);

    fireEvent.click(screen.getByRole("switch", { name: "Show resolved" }));
    expect(onChange).toHaveBeenCalledWith(true);

    rerender(<Switch checked label="Show resolved" onChange={onChange} />);
    fireEvent.click(screen.getByRole("switch", { name: "Show resolved" }));
    expect(onChange).toHaveBeenLastCalledWith(false);
  });

  it("stays named when the label is visually hidden", () => {
    render(<Switch checked={false} label="Live updates" hideLabel onChange={vi.fn()} />);

    expect(screen.getByRole("switch", { name: "Live updates" })).toBeInTheDocument();
  });

  it("does not toggle while disabled", () => {
    const onChange = vi.fn();
    render(<Switch checked={false} label="Show resolved" disabled onChange={onChange} />);

    fireEvent.click(screen.getByRole("switch", { name: "Show resolved" }));

    expect(onChange).not.toHaveBeenCalled();
    expect(screen.getByRole("switch")).toBeDisabled();
  });
});
