import type { Topology } from "../../api/schemas";

export const makeTopology = (overrides: Partial<Topology> = {}): Topology => ({
  generated_at: "2026-10-26T10:00:00Z",
  nodes: [
    { id: "s:1", kind: "switch", dpid: 1, port_no: null, label: "s1" },
    { id: "h:1:1", kind: "host", dpid: 1, port_no: 1, label: "h1" },
  ],
  edges: [{ source: "s:1", target: "h:1:1", source_port: 1, target_port: null }],
  ...overrides,
});
