import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { AlertsBadge } from "./AlertsBadge";

describe("AlertsBadge", () => {
  it("is positive with no open alerts", () => {
    render(<AlertsBadge summary={{ open: 0, critical: 0, warning: 0, acknowledged: 0 }} />);

    expect(screen.getByRole("status")).toHaveAttribute("data-tone", "positive");
    expect(screen.getByText("No alerts")).toBeInTheDocument();
  });

  it("is warning with open warnings only", () => {
    render(<AlertsBadge summary={{ open: 1, critical: 0, warning: 1, acknowledged: 0 }} />);

    expect(screen.getByRole("status")).toHaveAttribute("data-tone", "warning");
    expect(screen.getByText("1 alert")).toBeInTheDocument();
    expect(screen.queryByText(/critical/)).not.toBeInTheDocument();
  });

  it("is critical and counts criticals when any is open", () => {
    render(<AlertsBadge summary={{ open: 3, critical: 2, warning: 1, acknowledged: 1 }} />);

    expect(screen.getByRole("status")).toHaveAttribute("data-tone", "critical");
    expect(screen.getByText("3 alerts")).toBeInTheDocument();
    expect(screen.getByText("2 critical")).toBeInTheDocument();
  });
});
