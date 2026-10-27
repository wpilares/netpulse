import { act, fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";
import { App } from "./App";
import { ApiError } from "./api/client";
import type { Alert } from "./api/schemas";
import { makeAlert, makeAlertsFrame } from "./features/alerts/fixtures";
import { createFakeSocket, FakeSocket } from "./features/telemetry/fakeSocket";
import { makeKpiFrame, makePort, makeSnapshot } from "./features/telemetry/fixtures";
import { createFakeApiClient } from "./test/fakeApiClient";
import { renderWithProviders } from "./test/renderWithProviders";

const renderApp = (apiClient = createFakeApiClient()) =>
  renderWithProviders(<App createSocket={createFakeSocket} socketUrl="ws://test/ws/telemetry" />, { apiClient });

const deliver = async (payload: unknown): Promise<void> => {
  await act(async () => {
    FakeSocket.at(0).message(payload);
  });
};

describe("App", () => {
  beforeEach(() => {
    FakeSocket.reset();
  });

  it("paints the REST summary first, then follows live frames", async () => {
    renderApp(
      createFakeApiClient({ getKpiSummary: () => Promise.resolve(makeSnapshot([makePort({ rx_bps: 1_000_000 })])) }),
    );

    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("NetPulse");
    expect(await screen.findByText(/API online/)).toBeInTheDocument();
    await screen.findByText("1.0 Mb/s");
    expect(screen.getByText("Inbound throughput").nextElementSibling).toHaveTextContent("1.0 Mb/s");
    expect(await screen.findByRole("img", { name: /Network topology/ })).toBeInTheDocument();
    expect(screen.getByText("Connecting")).toBeInTheDocument();

    act(() => FakeSocket.at(0).open());
    await deliver(makeKpiFrame([makePort({ rx_bps: 3_000_000 })]));

    expect(screen.getByText("Live")).toBeInTheDocument();
    await waitFor(() =>
      expect(screen.getByText("Inbound throughput").nextElementSibling).toHaveTextContent("3.0 Mb/s"),
    );
    expect(screen.getByRole("button", { name: "Switch 1", pressed: true })).toBeInTheDocument();
    expect(screen.getByRole("img", { name: /Port 1 throughput/ })).toBeInTheDocument();
  });

  it("shows live alerts in the header badge and the alerts panel", async () => {
    renderApp();

    expect(await screen.findByText("No alerts")).toBeInTheDocument();
    expect(screen.getByText("No open alerts")).toBeInTheDocument();

    act(() => FakeSocket.at(0).open());
    await deliver(makeAlertsFrame([makeAlert({ id: 1, severity: "critical" })]));

    expect(screen.getByText("1 alert").closest("output")).toHaveAttribute("data-tone", "critical");
    expect(screen.getByRole("heading", { name: "Alerts" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Acknowledge" })).toBeInTheDocument();
    expect(screen.queryByText("No open alerts")).not.toBeInTheDocument();
  });

  it("acknowledges an alert optimistically and rolls back when the API rejects it", async () => {
    let fail: (error: Error) => void = () => undefined;
    const apiClient = createFakeApiClient({
      acknowledgeAlert: () =>
        new Promise<Alert>((_resolve, reject) => {
          fail = reject;
        }),
    });
    renderApp(apiClient);
    act(() => FakeSocket.at(0).open());
    await deliver(makeAlertsFrame([makeAlert({ id: 1 })]));

    fireEvent.click(await screen.findByRole("button", { name: "Acknowledge" }));

    await waitFor(() => expect(screen.getByText("1 acknowledged")).toBeInTheDocument());
    expect(screen.queryByRole("button", { name: "Acknowledge" })).not.toBeInTheDocument();
    expect(apiClient.acknowledgeAlert).toHaveBeenCalledWith(1);

    await act(async () => {
      fail(new ApiError("not_found", "missing", 404));
    });

    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("Alert not found"));
    expect(screen.getByText("0 acknowledged")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Acknowledge" })).toBeEnabled();
  });

  it("loads resolved alerts on demand", async () => {
    const resolved = makeAlert({ id: 9, status: "resolved", resolved_at: "2026-10-26T10:03:00Z" });
    const apiClient = createFakeApiClient({
      listAlerts: ({ status }) =>
        Promise.resolve({ generated_at: "2026-10-26T10:00:05Z", alerts: status === "resolved" ? [resolved] : [] }),
    });
    renderApp(apiClient);
    expect(await screen.findByText("No open alerts")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Show resolved alerts" }));

    expect(await screen.findByRole("list", { name: "Resolved alerts" })).toBeInTheDocument();
    expect(apiClient.listAlerts).toHaveBeenCalledWith({ status: "resolved", limit: 50 }, expect.any(AbortSignal));
  });
});
