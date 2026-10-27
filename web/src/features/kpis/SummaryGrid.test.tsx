import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { SummaryGrid, SummarySkeleton } from "./SummaryGrid";

describe("SummaryGrid", () => {
  it("renders every KPI as a stat tile with its value and tone", () => {
    render(
      <SummaryGrid
        summary={{
          ports: 12,
          switches: 3,
          rx_bps: 4_200_000,
          tx_bps: 900,
          drop_rate: 0.001,
          error_rate: 0,
          max_utilization: 0.95,
          counter_resets: 1,
        }}
      />,
    );

    expect(screen.getByText("Inbound throughput").nextElementSibling).toHaveTextContent("4.2 Mb/s");
    expect(screen.getByText("Outbound throughput").nextElementSibling).toHaveTextContent("900 b/s");
    expect(screen.getByText("Max utilization").closest("[data-tone]")).toHaveAttribute("data-tone", "critical");
    expect(screen.getByText("Drop rate").closest("[data-tone]")).toHaveAttribute("data-tone", "warning");
    expect(screen.getByText("Error rate").closest("[data-tone]")).toHaveAttribute("data-tone", "neutral");
    expect(screen.getByText("Switches").nextElementSibling).toHaveTextContent("3");
    expect(screen.getByText("Ports").nextElementSibling).toHaveTextContent("12");
    expect(screen.getByText("Counter resets").nextElementSibling).toHaveTextContent("1");
  });

  it("renders eight skeleton tiles while loading", () => {
    const { container } = render(<SummarySkeleton />);

    expect(screen.getByText("Loading network summary")).toBeInTheDocument();
    expect(container.querySelectorAll('[aria-hidden="true"]')).toHaveLength(8);
  });
});
