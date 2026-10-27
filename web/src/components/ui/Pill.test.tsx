import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Pill } from "./Pill";

describe("Pill", () => {
  it("shows the label and detail with the given tone", () => {
    render(<Pill tone="positive" label="Live" detail="updated 10:00:05" />);

    const pill = screen.getByText("Live").closest("[data-tone]");
    expect(pill).toHaveAttribute("data-tone", "positive");
    expect(pill).toHaveTextContent("updated 10:00:05");
  });

  it("omits the detail when it is null or missing", () => {
    render(<Pill tone="neutral" label="Connecting" detail={null} />);

    expect(screen.getByText("Connecting")).toBeInTheDocument();
    expect(screen.getByText("Connecting").parentElement?.childElementCount).toBe(2);
  });

  it("marks a pulsing pill and accepts an explicit role", () => {
    render(<Pill tone="critical" label="3 alerts" pulse role="status" />);

    const pill = screen.getByRole("status");
    expect(pill).toHaveAttribute("data-tone", "critical");
    expect(pill).toHaveAttribute("data-pulse", "true");
  });

  it("can render as an output element with an implicit status role", () => {
    render(<Pill as="output" tone="neutral" label="Connecting" />);

    const pill = screen.getByRole("status");
    expect(pill.tagName).toBe("OUTPUT");
  });
});
