import { act, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { App } from "./App";
import { makeAlert, makeAlertsFrame } from "./features/alerts/fixtures";
import { createFakeSocket, FakeSocket } from "./features/telemetry/fakeSocket";
import { makeKpiFrame, makePort, makeSnapshot } from "./features/telemetry/fixtures";

const topology = {
  generated_at: "2026-10-26T10:00:00Z",
  nodes: [
    { id: "s:1", kind: "switch", dpid: 1, port_no: null, label: "s1" },
    { id: "h:1:1", kind: "host", dpid: 1, port_no: 1, label: "h1" },
  ],
  edges: [{ source: "s:1", target: "h:1:1", source_port: 1, target_port: null }],
};

const requestUrl = (input: string | URL | Request): string =>
  typeof input === "string" ? input : input instanceof URL ? input.href : input.url;

const fakeFetch = vi.fn<typeof fetch>((input) => {
  switch (requestUrl(input)) {
    case "/health":
      return Promise.resolve(Response.json({ status: "ok", database: "up", version: "0.3.0" }));
    case "/api/v1/kpis/summary":
      return Promise.resolve(Response.json(makeSnapshot([makePort({ rx_bps: 1_000_000 })])));
    case "/api/v1/topology":
      return Promise.resolve(Response.json(topology));
    case "/api/v1/alerts?status=open&limit=100":
      return Promise.resolve(Response.json({ generated_at: "2026-10-26T10:00:00Z", alerts: [] }));
    default:
      return Promise.resolve(new Response(null, { status: 404 }));
  }
});

describe("App", () => {
  beforeEach(() => {
    FakeSocket.reset();
  });

  it("paints the REST summary first, then follows live frames", async () => {
    render(<App fetcher={fakeFetch} createSocket={createFakeSocket} socketUrl="ws://test/ws/telemetry" />);

    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("NetPulse");
    expect(await screen.findByText(/API online/)).toBeInTheDocument();
    await screen.findByText("1.0 Mb/s");
    expect(screen.getByText("Inbound throughput").nextElementSibling).toHaveTextContent("1.0 Mb/s");
    expect(await screen.findByRole("img", { name: /Network topology/ })).toBeInTheDocument();
    expect(screen.getByText("Connecting")).toBeInTheDocument();

    act(() => FakeSocket.at(0).open());
    act(() => FakeSocket.at(0).message(makeKpiFrame([makePort({ rx_bps: 3_000_000 })])));

    expect(screen.getByText("Live")).toBeInTheDocument();
    expect(screen.getByText("Inbound throughput").nextElementSibling).toHaveTextContent("3.0 Mb/s");
    expect(screen.getByRole("button", { name: "Switch 1", pressed: true })).toBeInTheDocument();
    expect(screen.getByRole("img", { name: /Port 1 throughput/ })).toBeInTheDocument();
  });

  it("shows live alerts in the header badge and the alerts panel", async () => {
    render(<App fetcher={fakeFetch} createSocket={createFakeSocket} socketUrl="ws://test/ws/telemetry" />);

    expect(await screen.findByText("No alerts")).toBeInTheDocument();
    expect(screen.getByText("No open alerts")).toBeInTheDocument();

    act(() => FakeSocket.at(0).open());
    act(() => FakeSocket.at(0).message(makeAlertsFrame([makeAlert({ id: 1, severity: "critical" })])));

    expect(screen.getByText("1 alert").closest("output")).toHaveAttribute("data-tone", "critical");
    expect(screen.getByRole("heading", { name: "Alerts" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Acknowledge" })).toBeInTheDocument();
    expect(screen.queryByText("No open alerts")).not.toBeInTheDocument();
  });
});
