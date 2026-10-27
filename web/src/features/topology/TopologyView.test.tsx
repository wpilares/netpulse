import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { makePort, makeSnapshot } from "../telemetry/fixtures";
import { TopologyView } from "./TopologyView";
import type { Topology } from "./topology";

const topology: Topology = {
  generated_at: "2026-10-26T10:00:00Z",
  nodes: [
    { id: "s:1", kind: "switch", dpid: 1, port_no: null, label: "s1" },
    { id: "s:2", kind: "switch", dpid: 2, port_no: null, label: "s2" },
    { id: "h:2:1", kind: "host", dpid: 2, port_no: 1, label: "h1" },
  ],
  edges: [
    { source: "s:1", target: "s:2", source_port: 1, target_port: 3 },
    { source: "s:2", target: "h:2:1", source_port: 1, target_port: null },
  ],
};

describe("TopologyView", () => {
  it("renders an accessible graph with labeled nodes, utilization-colored links and a legend", () => {
    const latest = makeSnapshot([makePort({ dpid: 1, port_no: 1, utilization: 0.95 })]);
    render(<TopologyView state={{ kind: "ready", topology }} latest={latest} />);

    expect(screen.getByRole("region", { name: "Topology" })).toBeInTheDocument();
    const graph = screen.getByRole("img", { name: "Network topology: 2 switches, 1 host" });
    expect(screen.getByText("s1")).toBeInTheDocument();
    expect(screen.getByText("h1")).toBeInTheDocument();
    expect(graph.querySelector('[data-level="saturated"]')).not.toBeNull();
    expect(graph.querySelector('[data-level="unknown"]')).not.toBeNull();

    const legend = screen.getByRole("list", { name: "Utilization levels" });
    expect(
      within(legend)
        .getAllByRole("listitem")
        .map((item) => item.textContent),
    ).toEqual(["Idle", "< 30%", "30–70%", "70–90%", "≥ 90%", "No data"]);
  });

  it("shows a skeleton while loading and an error with retry when unavailable", () => {
    const onRetry = vi.fn();
    const { rerender } = render(<TopologyView state={{ kind: "loading" }} latest={null} />);
    expect(screen.getByText(/Loading topology/)).toBeInTheDocument();

    rerender(<TopologyView state={{ kind: "unavailable" }} latest={null} onRetry={onRetry} />);
    expect(screen.getByRole("alert")).toHaveTextContent("Controller unreachable");
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });
});
