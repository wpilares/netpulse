import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { AlertsPanel, type AlertsPanelProps } from "./AlertsPanel";
import { alertSummary } from "./alerts";
import { makeAlert } from "./fixtures";

const now = Date.parse("2026-10-26T10:05:00Z");

const rowAt = (index: number): HTMLElement => {
  const row = screen.getAllByRole("listitem")[index];
  if (row === undefined) {
    throw new Error(`No alert row at index ${index}`);
  }
  return row;
};

const view = (overrides: Partial<AlertsPanelProps> = {}): AlertsPanelProps => {
  const alerts = overrides.alerts ?? [];
  return {
    alerts,
    summary: alertSummary(alerts),
    pending: new Set(),
    error: null,
    acknowledge: vi.fn(() => Promise.resolve()),
    resolved: { kind: "hidden" },
    toggleResolved: vi.fn(),
    now,
    ...overrides,
  };
};

describe("AlertsPanel", () => {
  it("shows the empty state and zero counts without alerts", () => {
    render(<AlertsPanel {...view()} />);

    expect(screen.getByText("No open alerts")).toBeInTheDocument();
    expect(screen.getByText("0 critical")).toHaveAttribute("data-tone", "critical");
    expect(screen.getByText("0 warning")).toHaveAttribute("data-tone", "warning");
    expect(screen.queryByRole("button", { name: "Acknowledge" })).not.toBeInTheDocument();
  });

  it("renders one row per open alert with severity, figures and an acknowledge action", () => {
    const props = view({
      alerts: [
        makeAlert({ id: 1, severity: "critical", opened_at: "2026-10-26T10:00:00Z" }),
        makeAlert({
          id: 2,
          dpid: 3,
          port_no: 4,
          metric: "drop_rate",
          value: 0.052,
          expected: 0.001,
          zscore: 7.2,
          acknowledged_at: "2026-10-26T10:01:00Z",
          opened_at: "2026-10-26T10:04:30Z",
        }),
      ],
    });
    render(<AlertsPanel {...props} />);

    expect(screen.getByText("1 critical")).toBeInTheDocument();
    expect(screen.getByText("1 warning")).toBeInTheDocument();
    expect(screen.getByText("1 acknowledged")).toBeInTheDocument();

    expect(screen.getAllByRole("listitem")).toHaveLength(2);

    const critical = within(rowAt(0));
    expect(rowAt(0)).toHaveAccessibleName("Port 2 on switch 1: rx_bps 9.4 Mb/s, expected 1.2 Mb/s (z 6.5)");
    expect(critical.getByText("critical")).toHaveAttribute("data-tone", "critical");
    expect(critical.getByText("Switch 1 · Port 2")).toBeInTheDocument();
    expect(critical.getByText("9.4 Mb/s")).toBeInTheDocument();
    expect(critical.getByText("1.2 Mb/s")).toBeInTheDocument();
    expect(critical.getByText("6.5")).toBeInTheDocument();
    expect(critical.getByText("5 min ago")).toBeInTheDocument();
    fireEvent.click(critical.getByRole("button", { name: "Acknowledge" }));
    expect(props.acknowledge).toHaveBeenCalledWith(1);

    const acknowledged = within(rowAt(1));
    expect(rowAt(1)).toHaveAttribute("data-acknowledged", "true");
    expect(acknowledged.getByText("warning")).toHaveAttribute("data-tone", "warning");
    expect(acknowledged.getByText("5.2%")).toBeInTheDocument();
    expect(acknowledged.getByText("30 s ago")).toBeInTheDocument();
    expect(acknowledged.getByText("Acknowledged")).toBeInTheDocument();
    expect(acknowledged.queryByRole("button", { name: "Acknowledge" })).not.toBeInTheDocument();
  });

  it("disables the acknowledge button while the request is pending", () => {
    render(<AlertsPanel {...view({ alerts: [makeAlert({ id: 1 })], pending: new Set([1]) })} />);

    expect(screen.getByRole("button", { name: "Acknowledge" })).toBeDisabled();
  });

  it("surfaces the API error", () => {
    render(<AlertsPanel {...view({ error: "Alert storage unavailable" })} />);

    expect(screen.getByRole("alert")).toHaveTextContent("Alert storage unavailable");
  });

  it("toggles resolved alerts and lists them when loaded", () => {
    const props = view();
    const { rerender } = render(<AlertsPanel {...props} />);

    const toggle = screen.getByRole("button", { name: "Show resolved alerts" });
    expect(toggle).toHaveAttribute("aria-pressed", "false");
    fireEvent.click(toggle);
    expect(props.toggleResolved).toHaveBeenCalledTimes(1);

    rerender(<AlertsPanel {...props} resolved={{ kind: "loading" }} />);
    expect(screen.getByRole("button", { name: "Hide resolved alerts" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByText("Loading resolved alerts…")).toBeInTheDocument();

    const resolved = makeAlert({ id: 5, status: "resolved", resolved_at: "2026-10-26T10:03:00Z" });
    rerender(<AlertsPanel {...props} resolved={{ kind: "ready", alerts: [resolved] }} />);
    const list = screen.getByRole("list", { name: "Resolved alerts" });
    expect(within(list).getAllByRole("listitem")).toHaveLength(1);
    expect(within(list).getByText("Resolved 2 min ago")).toBeInTheDocument();
    expect(within(list).queryByRole("button", { name: "Acknowledge" })).not.toBeInTheDocument();

    rerender(<AlertsPanel {...props} resolved={{ kind: "ready", alerts: [] }} />);
    expect(screen.getByText("No resolved alerts")).toBeInTheDocument();

    rerender(<AlertsPanel {...props} resolved={{ kind: "unavailable", reason: "Alert storage unavailable" }} />);
    expect(screen.getByRole("alert")).toHaveTextContent("Alert storage unavailable");
  });
});
