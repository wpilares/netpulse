import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { makePort } from "../telemetry/fixtures";
import { PortChart } from "./PortChart";

describe("PortChart", () => {
  it("renders rx and tx series with the latest values in the legend", () => {
    const points = [
      makePort({ computed_at: "2026-10-26T10:00:00Z", rx_bps: 1_000_000, tx_bps: 250_000 }),
      makePort({ computed_at: "2026-10-26T10:00:05Z", rx_bps: null, tx_bps: 300_000 }),
      makePort({ computed_at: "2026-10-26T10:00:10Z", rx_bps: 2_000_000, tx_bps: 350_000 }),
    ];
    render(<PortChart portNo={1} points={points} />);

    const chart = screen.getByRole("img", { name: /Port 1 throughput, 3 samples/ });
    expect(chart.querySelectorAll("path[data-series]")).toHaveLength(2);
    expect(chart.querySelector('[data-series="rx"]')?.getAttribute("d")).toMatch(/^M.*M/);
    expect(screen.getByText("2.0 Mb/s", { selector: "strong" })).toBeInTheDocument();
    expect(screen.getByText("350.0 kb/s", { selector: "strong" })).toBeInTheDocument();
  });

  it("shows a waiting message when there are no samples", () => {
    render(<PortChart portNo={2} points={[]} />);

    expect(screen.getByRole("img", { name: /Port 2 throughput/ })).toBeInTheDocument();
    expect(screen.getByText("Waiting for samples")).toBeInTheDocument();
    expect(screen.getAllByText("—", { selector: "strong" })).toHaveLength(2);
  });
});
