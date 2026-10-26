import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
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
  it("renders an accessible graph with labeled nodes and utilization-colored links", () => {
    const latest = makeSnapshot([makePort({ dpid: 1, port_no: 1, utilization: 0.95 })]);
    render(<TopologyView state={{ kind: "ready", topology }} latest={latest} />);

    const graph = screen.getByRole("img", { name: "Network topology: 2 switches, 1 host" });
    expect(graph).toBeInTheDocument();
    expect(screen.getByText("s1")).toBeInTheDocument();
    expect(screen.getByText("h1")).toBeInTheDocument();
    expect(graph.querySelector('[data-level="saturated"]')).not.toBeNull();
    expect(graph.querySelector('[data-level="unknown"]')).not.toBeNull();
  });

  it("explains loading and unavailable states", () => {
    const { rerender } = render(<TopologyView state={{ kind: "loading" }} latest={null} />);
    expect(screen.getByText(/Loading topology/)).toBeInTheDocument();

    rerender(<TopologyView state={{ kind: "unavailable" }} latest={null} />);
    expect(screen.getByText(/controller unreachable/)).toBeInTheDocument();
  });
});
