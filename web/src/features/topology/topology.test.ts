import { describe, expect, it, vi } from "vitest";
import { makePort, makeSnapshot } from "../telemetry/fixtures";
import {
  edgeUtilization,
  fetchTopology,
  layoutTopology,
  parseTopology,
  type Topology,
  utilizationByPort,
  utilizationLevel,
} from "./topology";

const treeTopology: Topology = {
  generated_at: "2026-10-26T10:00:00Z",
  nodes: [
    { id: "s:1", kind: "switch", dpid: 1, port_no: null, label: "s1" },
    { id: "s:2", kind: "switch", dpid: 2, port_no: null, label: "s2" },
    { id: "s:3", kind: "switch", dpid: 3, port_no: null, label: "s3" },
    { id: "h:2:1", kind: "host", dpid: 2, port_no: 1, label: "h1" },
    { id: "h:2:2", kind: "host", dpid: 2, port_no: 2, label: "h2" },
    { id: "h:3:1", kind: "host", dpid: 3, port_no: 1, label: "h3" },
    { id: "h:3:2", kind: "host", dpid: 3, port_no: 2, label: "h4" },
  ],
  edges: [
    { source: "s:1", target: "s:2", source_port: 1, target_port: 3 },
    { source: "s:2", target: "s:1", source_port: 3, target_port: 1 },
    { source: "s:1", target: "s:3", source_port: 2, target_port: 3 },
    { source: "s:3", target: "s:1", source_port: 3, target_port: 2 },
    { source: "s:2", target: "h:2:1", source_port: 1, target_port: null },
    { source: "s:2", target: "h:2:2", source_port: 2, target_port: null },
    { source: "s:3", target: "h:3:1", source_port: 1, target_port: null },
    { source: "s:3", target: "h:3:2", source_port: 2, target_port: null },
  ],
};

describe("parseTopology", () => {
  it("accepts the API payload", () => {
    expect(parseTopology(treeTopology)).toEqual(treeTopology);
  });

  it.each([
    null,
    { nodes: [] },
    { ...treeTopology, nodes: [{ id: "x" }] },
    { ...treeTopology, edges: [{ source: 1 }] },
  ])("rejects malformed payload %j", (payload) => {
    expect(parseTopology(payload)).toBeNull();
  });
});

describe("fetchTopology", () => {
  it("returns the parsed topology", async () => {
    const fetcher = vi.fn<typeof fetch>().mockResolvedValue(Response.json(treeTopology));
    await expect(fetchTopology(fetcher)).resolves.toEqual({ kind: "ready", topology: treeTopology });
    expect(fetcher).toHaveBeenCalledWith(
      "/api/v1/topology",
      expect.objectContaining({ headers: { Accept: "application/json" } }),
    );
  });

  it("reports the controller as unavailable on 503 or network failure", async () => {
    const unavailable = vi.fn<typeof fetch>().mockResolvedValue(Response.json({ detail: "down" }, { status: 503 }));
    await expect(fetchTopology(unavailable)).resolves.toEqual({ kind: "unavailable" });

    const failing = vi.fn<typeof fetch>().mockRejectedValue(new TypeError("offline"));
    await expect(fetchTopology(failing)).resolves.toEqual({ kind: "unavailable" });
  });
});

describe("layoutTopology", () => {
  const size = { width: 800, height: 400 };

  it("places switches in BFS layers from the lowest dpid and hosts in a bottom row", () => {
    const layout = layoutTopology(treeTopology, size);
    const byId = new Map(layout.nodes.map((node) => [node.id, node]));
    const s1 = byId.get("s:1");
    const s2 = byId.get("s:2");
    const s3 = byId.get("s:3");
    const h1 = byId.get("h:2:1");
    const h4 = byId.get("h:3:2");

    expect(s1?.depth).toBe(0);
    expect(s2?.depth).toBe(1);
    expect(s3?.depth).toBe(1);
    expect(s1?.y).toBeLessThan(s2?.y ?? 0);
    expect(s2?.y).toBe(s3?.y);
    expect(s2?.x).toBeLessThan(s3?.x ?? 0);
    expect(h1?.y).toBeGreaterThan(s2?.y ?? 0);
    expect(h1?.x).toBeLessThan(h4?.x ?? 0);
    expect(s1?.x).toBe(400);
  });

  it("spaces hosts evenly and keeps them under their parent switch", () => {
    const layout = layoutTopology(treeTopology, size);
    const hosts = layout.nodes.filter((node) => node.kind === "host").map((node) => node.x);
    expect(hosts).toEqual([160, 320, 480, 640]);
  });

  it("deduplicates directed switch links and positions edges", () => {
    const layout = layoutTopology(treeTopology, size);
    const switchEdges = layout.edges.filter((edge) => edge.source.startsWith("s:") && edge.target.startsWith("s:"));
    expect(switchEdges).toHaveLength(2);
    expect(layout.edges).toHaveLength(6);
    const first = switchEdges[0];
    expect(first?.x1).toBe(400);
    expect(first?.y2).toBeGreaterThan(first?.y1 ?? 0);
  });

  it("is deterministic regardless of input order", () => {
    const reversed: Topology = {
      ...treeTopology,
      nodes: [...treeTopology.nodes].reverse(),
      edges: [...treeTopology.edges].reverse(),
    };
    expect(layoutTopology(reversed, size)).toEqual(layoutTopology(treeTopology, size));
  });

  it("handles an empty topology", () => {
    const layout = layoutTopology({ generated_at: "2026-10-26T10:00:00Z", nodes: [], edges: [] }, size);
    expect(layout.nodes).toEqual([]);
    expect(layout.edges).toEqual([]);
  });
});

describe("utilizationLevel", () => {
  it("buckets utilization ratios", () => {
    expect(utilizationLevel(null)).toBe("unknown");
    expect(utilizationLevel(0)).toBe("idle");
    expect(utilizationLevel(0.2)).toBe("low");
    expect(utilizationLevel(0.5)).toBe("medium");
    expect(utilizationLevel(0.8)).toBe("high");
    expect(utilizationLevel(0.95)).toBe("saturated");
  });
});

describe("edgeUtilization", () => {
  it("takes the busiest direction known for the link", () => {
    const lookup = utilizationByPort(
      makeSnapshot([
        makePort({ dpid: 1, port_no: 1, utilization: 0.2 }),
        makePort({ dpid: 2, port_no: 3, utilization: 0.7 }),
      ]),
    );
    const edge = { source: "s:1", target: "s:2", source_port: 1, target_port: 3 };
    expect(edgeUtilization(edge, lookup)).toBe(0.7);
    expect(edgeUtilization({ ...edge, target_port: null }, lookup)).toBe(0.2);
    expect(edgeUtilization({ source: "s:9", target: "s:8", source_port: 1, target_port: 1 }, lookup)).toBeNull();
  });
});
