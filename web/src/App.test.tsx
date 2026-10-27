import { act, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { App } from "./App";
import { ApiError } from "./api/client";
import type { Alert, AlertList } from "./api/schemas";
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

const tileValue = (label: string): Element | null => screen.getByText(label).nextElementSibling;

describe("App", () => {
  beforeEach(() => {
    FakeSocket.reset();
  });

  afterEach(() => {
    localStorage.clear();
    document.documentElement.removeAttribute("data-theme");
  });

  it("renders the shell landmarks, the four panels and the theme toggle", async () => {
    renderApp();

    const header = screen.getByRole("banner");
    expect(within(header).getByRole("heading", { level: 1 })).toHaveTextContent("NetPulse");
    expect(within(header).getByRole("radiogroup", { name: "Theme" })).toBeInTheDocument();
    const main = screen.getByRole("main");
    expect(within(main).getByRole("region", { name: "Network summary" })).toBeInTheDocument();
    expect(within(main).getByRole("region", { name: "Alerts" })).toBeInTheDocument();
    expect(within(main).getByRole("region", { name: "Topology" })).toBeInTheDocument();
    expect(within(main).getByRole("region", { name: "Switch ports" })).toBeInTheDocument();
    expect(await within(screen.getByRole("contentinfo")).findByText("API v1.0.0")).toBeInTheDocument();
  });

  it("paints the REST summary first, then follows live frames", async () => {
    renderApp(
      createFakeApiClient({ getKpiSummary: () => Promise.resolve(makeSnapshot([makePort({ rx_bps: 1_000_000 })])) }),
    );

    expect(screen.getByText("Loading network summary")).toBeInTheDocument();
    expect(await screen.findByText(/API online/)).toBeInTheDocument();
    await screen.findByText("1.0 Mb/s");
    expect(tileValue("Inbound throughput")).toHaveTextContent("1.0 Mb/s");
    expect(await screen.findByRole("img", { name: /Network topology/ })).toBeInTheDocument();
    expect(screen.getByText("Connecting")).toBeInTheDocument();

    act(() => FakeSocket.at(0).open());
    await deliver(makeKpiFrame([makePort({ rx_bps: 3_000_000 })]));

    expect(screen.getByText("Live")).toBeInTheDocument();
    await waitFor(() => expect(tileValue("Inbound throughput")).toHaveTextContent("3.0 Mb/s"));
    expect(screen.getByRole("radio", { name: "Switch 1" })).toBeChecked();
    expect(screen.getByRole("img", { name: /Port 1 throughput/ })).toBeInTheDocument();
  });

  it("shows an error state with retry when the summary cannot be loaded", async () => {
    let calls = 0;
    const apiClient = createFakeApiClient({
      getKpiSummary: () => {
        calls += 1;
        return calls === 1
          ? Promise.reject(new ApiError("unavailable", "down", 503))
          : Promise.resolve(makeSnapshot([makePort({ rx_bps: 5_000_000 })]));
      },
    });
    renderApp(apiClient);

    const summary = screen.getByRole("region", { name: "Network summary" });
    expect(await within(summary).findByRole("alert")).toHaveTextContent("Network summary unavailable");

    fireEvent.click(within(summary).getByRole("button", { name: "Retry" }));

    expect(await within(summary).findByText("5.0 Mb/s")).toBeInTheDocument();
  });

  it("shows live alerts in the header badge and the alerts panel", async () => {
    renderApp();

    expect(await screen.findByText("No alerts")).toBeInTheDocument();
    expect(screen.getByText("No open alerts")).toBeInTheDocument();

    act(() => FakeSocket.at(0).open());
    await deliver(makeAlertsFrame([makeAlert({ id: 1, severity: "critical" })]));

    const badge = await screen.findByText("1 alert", undefined, { timeout: 2000 });
    expect(badge.closest("output")).toHaveAttribute("data-tone", "critical");
    expect(screen.getByRole("heading", { name: "Alerts" })).toBeInTheDocument();
    expect(await screen.findByRole("button", { name: "Acknowledge" })).toBeInTheDocument();
    expect(screen.queryByText("No open alerts")).not.toBeInTheDocument();
  });

  it("keeps the live alerts when the REST list resolves after the first frame", async () => {
    let respond: (list: AlertList) => void = () => undefined;
    const apiClient = createFakeApiClient({
      listAlerts: () =>
        new Promise<AlertList>((resolve) => {
          respond = resolve;
        }),
    });
    renderApp(apiClient);
    act(() => FakeSocket.at(0).open());
    await deliver(makeAlertsFrame([makeAlert({ id: 1, severity: "critical" })]));
    expect(await screen.findByText("1 alert", undefined, { timeout: 2000 })).toBeInTheDocument();

    await act(async () => {
      respond({ generated_at: "2026-10-26T10:00:00Z", alerts: [makeAlert({ id: 9, dpid: 9, port_no: 9 })] });
    });

    expect(await screen.findByText("1 alert", undefined, { timeout: 2000 })).toBeInTheDocument();
    expect(within(screen.getByRole("list", { name: "Open alerts" })).getAllByRole("listitem")).toHaveLength(1);
    expect(screen.queryByText("Switch 9 · Port 9")).not.toBeInTheDocument();
    expect(apiClient.listAlerts).toHaveBeenCalledTimes(1);
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

  it("loads resolved alerts on demand through the status filter", async () => {
    const resolved = makeAlert({ id: 9, status: "resolved", resolved_at: "2026-10-26T10:03:00Z" });
    const apiClient = createFakeApiClient({
      listAlerts: ({ status }) =>
        Promise.resolve({ generated_at: "2026-10-26T10:00:05Z", alerts: status === "resolved" ? [resolved] : [] }),
    });
    renderApp(apiClient);
    expect(await screen.findByText("No open alerts")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("radio", { name: "Resolved" }));

    expect(await screen.findByRole("list", { name: "Resolved alerts" })).toBeInTheDocument();
    expect(apiClient.listAlerts).toHaveBeenCalledWith({ status: "resolved", limit: 50 }, expect.any(AbortSignal));
  });
});
