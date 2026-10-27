import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { StatTile } from "./StatTile";

describe("StatTile", () => {
  it("shows label, value and hint with a neutral tone by default", () => {
    render(<StatTile label="Switches" value="4" hint="2 hosts" />);

    const tile = screen.getByText("Switches").closest("[data-tone]");
    expect(tile).toHaveAttribute("data-tone", "neutral");
    expect(tile).toHaveTextContent("4");
    expect(tile).toHaveTextContent("2 hosts");
  });

  it("carries the given tone and omits a missing hint", () => {
    render(<StatTile label="Open alerts" value={3} tone="critical" />);

    const tile = screen.getByText("Open alerts").closest("[data-tone]");
    expect(tile).toHaveAttribute("data-tone", "critical");
    expect(tile?.childElementCount).toBe(2);
  });
});
