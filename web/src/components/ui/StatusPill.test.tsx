import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { Tone } from "../tone";
import { StatusPill } from "./StatusPill";

describe("StatusPill", () => {
  it("is a polite live status region", () => {
    render(<StatusPill tone="positive" label="Live" detail="updated 10:00:05" />);

    const pill = screen.getByRole("status");
    expect(pill.tagName).toBe("OUTPUT");
    expect(pill).toHaveAttribute("aria-live", "polite");
    expect(pill).toHaveTextContent("Live");
    expect(pill).toHaveTextContent("updated 10:00:05");
  });

  it.each<Tone>(["neutral", "positive", "warning", "critical"])("maps the %s tone to data-tone", (tone) => {
    render(<StatusPill tone={tone} label="State" />);

    expect(screen.getByRole("status")).toHaveAttribute("data-tone", tone);
  });

  it("pulses only when asked", () => {
    const { rerender } = render(<StatusPill tone="critical" label="3 alerts" />);
    expect(screen.getByRole("status")).not.toHaveAttribute("data-pulse");

    rerender(<StatusPill tone="critical" label="3 alerts" pulse />);
    expect(screen.getByRole("status")).toHaveAttribute("data-pulse", "true");
  });
});
