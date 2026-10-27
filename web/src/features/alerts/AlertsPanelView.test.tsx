import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { AlertsPanelView, type AlertsPanelViewProps } from "./AlertsPanelView";
import { alertSummary } from "./alerts";
import { makeAlert } from "./fixtures";

const now = Date.parse("2026-10-26T10:05:00Z");

const view = (overrides: Partial<AlertsPanelViewProps> = {}): AlertsPanelViewProps => {
  const alerts = overrides.alerts ?? [];
  return {
    alerts,
    summary: alertSummary(alerts),
    pending: new Set(),
    error: null,
    acknowledge: vi.fn(() => Promise.resolve()),
    filter: "open",
    setFilter: vi.fn(),
    resolved: { kind: "hidden" },
    now,
    ...overrides,
  };
};

describe("AlertsPanelView", () => {
  it("is a labelled region with the empty state and zero counts", () => {
    render(<AlertsPanelView {...view()} />);

    expect(screen.getByRole("region", { name: "Alerts" })).toBeInTheDocument();
    expect(screen.getByText("No open alerts")).toBeInTheDocument();
    expect(screen.getByText("0 critical")).toHaveAttribute("data-tone", "critical");
    expect(screen.getByText("0 warning")).toHaveAttribute("data-tone", "warning");
    expect(screen.getByText("0 acknowledged")).toHaveAttribute("data-tone", "neutral");
    expect(screen.queryByRole("button", { name: "Acknowledge" })).not.toBeInTheDocument();
  });

  it("lists open alerts with counts and forwards acknowledgements", () => {
    const props = view({
      alerts: [
        makeAlert({ id: 1, severity: "critical" }),
        makeAlert({ id: 2, acknowledged_at: "2026-10-26T10:01:00Z", opened_at: "2026-10-26T10:04:30Z" }),
      ],
      pending: new Set([2]),
    });
    render(<AlertsPanelView {...props} />);

    expect(screen.getByText("1 critical")).toBeInTheDocument();
    expect(screen.getByText("1 warning")).toBeInTheDocument();
    expect(screen.getByText("1 acknowledged")).toBeInTheDocument();
    const list = screen.getByRole("list", { name: "Open alerts" });
    expect(within(list).getAllByRole("listitem")).toHaveLength(2);

    fireEvent.click(screen.getByRole("button", { name: "Acknowledge" }));

    expect(props.acknowledge).toHaveBeenCalledWith(1);
  });

  it("switches between open and resolved alerts with the segmented filter", () => {
    const props = view();
    render(<AlertsPanelView {...props} />);

    const filter = screen.getByRole("radiogroup", { name: "Alert status" });
    expect(within(filter).getByRole("radio", { name: "Open" })).toBeChecked();

    fireEvent.click(within(filter).getByRole("radio", { name: "Resolved" }));

    expect(props.setFilter).toHaveBeenCalledWith("resolved");
  });

  it("renders the resolved states: loading, ready, empty and unavailable", () => {
    const props = view({ filter: "resolved" });
    const { rerender } = render(<AlertsPanelView {...props} resolved={{ kind: "loading" }} />);
    expect(screen.getByText("Loading resolved alerts…")).toBeInTheDocument();

    const resolved = makeAlert({ id: 5, status: "resolved", resolved_at: "2026-10-26T10:03:00Z" });
    rerender(<AlertsPanelView {...props} resolved={{ kind: "ready", alerts: [resolved] }} />);
    const list = screen.getByRole("list", { name: "Resolved alerts" });
    expect(within(list).getByText("Resolved 2 min ago")).toBeInTheDocument();
    expect(within(list).queryByRole("button", { name: "Acknowledge" })).not.toBeInTheDocument();

    rerender(<AlertsPanelView {...props} resolved={{ kind: "ready", alerts: [] }} />);
    expect(screen.getByText("No resolved alerts")).toBeInTheDocument();

    rerender(<AlertsPanelView {...props} resolved={{ kind: "unavailable", reason: "Alert storage unavailable" }} />);
    expect(screen.getByRole("alert")).toHaveTextContent("Alert storage unavailable");
  });

  it("surfaces API errors above the list", () => {
    render(<AlertsPanelView {...view({ alerts: [makeAlert({ id: 1 })], error: "Alert not found" })} />);

    expect(screen.getByRole("alert")).toHaveTextContent("Alert not found");
    expect(screen.getByRole("button", { name: "Acknowledge" })).toBeInTheDocument();
  });
});
