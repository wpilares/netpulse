import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { AlertRow } from "./AlertRow";
import { makeAlert } from "./fixtures";

const now = Date.parse("2026-10-26T10:05:00Z");

describe("AlertRow", () => {
  it("shows severity, target, metric, figures and acknowledges on click", () => {
    const onAcknowledge = vi.fn();
    render(
      <ul>
        <AlertRow alert={makeAlert({ id: 1, severity: "critical" })} now={now} onAcknowledge={onAcknowledge} />
      </ul>,
    );

    const row = screen.getByRole("listitem");
    expect(row).toHaveAccessibleName("Port 2 on switch 1: rx_bps 9.4 Mb/s, expected 1.2 Mb/s (z 6.5)");
    expect(row).toHaveAttribute("data-tone", "critical");
    expect(screen.getByText("critical")).toHaveAttribute("data-tone", "critical");
    expect(screen.getByText("Switch 1 · Port 2")).toBeInTheDocument();
    expect(screen.getByText("rx_bps")).toHaveAttribute("data-tone", "neutral");
    expect(screen.getByText("9.4 Mb/s")).toBeInTheDocument();
    expect(screen.getByText("1.2 Mb/s")).toBeInTheDocument();
    expect(screen.getByText("6.5")).toBeInTheDocument();
    expect(screen.getByText("5 min ago")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Acknowledge" }));

    expect(onAcknowledge).toHaveBeenCalledWith(1);
  });

  it("marks the button busy while the acknowledgement is pending", () => {
    render(
      <ul>
        <AlertRow alert={makeAlert({ id: 1 })} now={now} pending onAcknowledge={vi.fn()} />
      </ul>,
    );

    const button = screen.getByRole("button", { name: "Acknowledge" });
    expect(button).toBeDisabled();
    expect(button).toHaveAttribute("aria-busy", "true");
  });

  it("replaces the action with a mark for acknowledged and resolved alerts", () => {
    const { rerender } = render(
      <ul>
        <AlertRow alert={makeAlert({ acknowledged_at: "2026-10-26T10:01:00Z" })} now={now} onAcknowledge={vi.fn()} />
      </ul>,
    );

    expect(screen.getByRole("listitem")).toHaveAttribute("data-acknowledged", "true");
    expect(screen.getByText("Acknowledged")).toBeInTheDocument();
    expect(screen.queryByRole("button")).not.toBeInTheDocument();

    rerender(
      <ul>
        <AlertRow alert={makeAlert({ status: "resolved", resolved_at: "2026-10-26T10:03:00Z" })} now={now} />
      </ul>,
    );

    expect(screen.getByText("Resolved 2 min ago")).toBeInTheDocument();
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });
});
