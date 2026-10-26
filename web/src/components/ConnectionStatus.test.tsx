import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ConnectionStatus } from "./ConnectionStatus";

describe("ConnectionStatus", () => {
  it("shows a live badge with the last update time", () => {
    const at = new Date(2026, 9, 26, 10, 0, 5).toISOString();
    render(<ConnectionStatus status="open" attempt={0} storeUnavailable={false} lastUpdateAt={at} />);

    const badge = screen.getByRole("status");
    expect(badge).toHaveTextContent("Live");
    expect(badge).toHaveTextContent("updated 10:00:05");
    expect(badge).toHaveAttribute("data-tone", "positive");
  });

  it("warns when the store is unavailable", () => {
    render(<ConnectionStatus status="open" attempt={0} storeUnavailable={true} lastUpdateAt={null} />);

    expect(screen.getByRole("status")).toHaveTextContent("store unavailable");
    expect(screen.getByRole("status")).toHaveAttribute("data-tone", "warning");
  });

  it("shows the reconnect attempt", () => {
    render(<ConnectionStatus status="reconnecting" attempt={3} storeUnavailable={false} lastUpdateAt={null} />);

    expect(screen.getByRole("status")).toHaveTextContent("Reconnecting (attempt 3)");
    expect(screen.getByRole("status")).toHaveAttribute("data-tone", "warning");
  });

  it("shows connecting and disconnected states", () => {
    const { rerender } = render(
      <ConnectionStatus status="connecting" attempt={0} storeUnavailable={false} lastUpdateAt={null} />,
    );
    expect(screen.getByRole("status")).toHaveTextContent("Connecting");

    rerender(<ConnectionStatus status="closed" attempt={0} storeUnavailable={false} lastUpdateAt={null} />);
    expect(screen.getByRole("status")).toHaveTextContent("Disconnected");
    expect(screen.getByRole("status")).toHaveAttribute("data-tone", "critical");
  });
});
