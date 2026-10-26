import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { SummaryCards } from "./SummaryCards";

describe("SummaryCards", () => {
  it("renders every network KPI as a labeled card", () => {
    render(
      <SummaryCards
        summary={{
          ports: 12,
          switches: 3,
          rx_bps: 4_200_000,
          tx_bps: 900,
          drop_rate: 0.001,
          error_rate: 0,
          max_utilization: 0.42,
          counter_resets: 1,
        }}
      />,
    );

    expect(screen.getByText("Inbound throughput").nextElementSibling).toHaveTextContent("4.2 Mb/s");
    expect(screen.getByText("Outbound throughput").nextElementSibling).toHaveTextContent("900 b/s");
    expect(screen.getByText("Max utilization").nextElementSibling).toHaveTextContent("42.0%");
    expect(screen.getByText("Drop rate").nextElementSibling).toHaveTextContent("0.1%");
    expect(screen.getByText("Error rate").nextElementSibling).toHaveTextContent("0.0%");
    expect(screen.getByText("Switches").nextElementSibling).toHaveTextContent("3");
    expect(screen.getByText("Ports").nextElementSibling).toHaveTextContent("12");
    expect(screen.getByText("Counter resets").nextElementSibling).toHaveTextContent("1");
  });

  it("shows an em dash for missing values", () => {
    render(
      <SummaryCards
        summary={{
          ports: 0,
          switches: 0,
          rx_bps: null,
          tx_bps: null,
          drop_rate: null,
          error_rate: null,
          max_utilization: null,
          counter_resets: 0,
        }}
      />,
    );

    expect(screen.getAllByText("—")).toHaveLength(5);
  });

  it("renders placeholders before the first snapshot", () => {
    render(<SummaryCards summary={null} />);

    expect(screen.getAllByText("—")).toHaveLength(8);
  });
});
