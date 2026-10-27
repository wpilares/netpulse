import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { makePort, makeSnapshot } from "../telemetry/fixtures";
import { SummaryPanelView } from "./SummaryPanel";

describe("SummaryPanelView", () => {
  it("is a labelled region showing skeleton tiles while loading", () => {
    render(<SummaryPanelView snapshot={null} status="loading" retry={vi.fn()} />);

    expect(screen.getByRole("region", { name: "Network summary" })).toBeInTheDocument();
    expect(screen.getByText("Loading network summary")).toBeInTheDocument();
  });

  it("shows an error state with a retry action when the summary is unavailable", () => {
    const retry = vi.fn();
    render(<SummaryPanelView snapshot={null} status="unavailable" retry={retry} />);

    expect(screen.getByRole("alert")).toHaveTextContent("Network summary unavailable");
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(retry).toHaveBeenCalledTimes(1);
  });

  it("renders the tiles and the snapshot time when ready", () => {
    const snapshot = makeSnapshot([makePort({ rx_bps: 2_000_000 })], new Date(2026, 9, 26, 10, 0, 5).toISOString());
    render(<SummaryPanelView snapshot={snapshot} status="ready" retry={vi.fn()} />);

    expect(screen.getByText("Inbound throughput").nextElementSibling).toHaveTextContent("2.0 Mb/s");
    expect(screen.getByText(/Updated/)).toHaveTextContent("10:00:05");
  });
});
