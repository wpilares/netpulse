import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Badge } from "./Badge";

describe("Badge", () => {
  it("is a soft neutral badge by default", () => {
    render(<Badge>3 open</Badge>);

    const badge = screen.getByText("3 open");
    expect(badge).toHaveAttribute("data-tone", "neutral");
    expect(badge).toHaveAttribute("data-variant", "soft");
  });

  it("exposes tone and variant", () => {
    render(
      <Badge tone="critical" variant="solid">
        Critical
      </Badge>,
    );

    const badge = screen.getByText("Critical");
    expect(badge).toHaveAttribute("data-tone", "critical");
    expect(badge).toHaveAttribute("data-variant", "solid");
  });

  it("passes through extra attributes", () => {
    render(<Badge title="Open alerts">2</Badge>);

    expect(screen.getByText("2")).toHaveAttribute("title", "Open alerts");
  });
});
