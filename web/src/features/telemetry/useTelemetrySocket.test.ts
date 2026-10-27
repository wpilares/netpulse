import { act } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { queryKeys } from "../../api/keys";
import type { AlertList, KpiSnapshot } from "../../api/schemas";
import { renderHookWithProviders } from "../../test/renderWithProviders";
import { makeAlert, makeAlertsFrame } from "../alerts/fixtures";
import { createFakeSocket, FakeSocket } from "./fakeSocket";
import { makeKpiFrame, makePort } from "./fixtures";
import { reconnectDelayMs, telemetrySocketUrl, useTelemetrySocket } from "./useTelemetrySocket";

const backoff = { baseMs: 1000, maxMs: 4000, jitterMs: 0 };

const renderSocket = () =>
  renderHookWithProviders(() =>
    useTelemetrySocket({
      url: "ws://test/ws/telemetry",
      createSocket: createFakeSocket,
      backoff,
      random: () => 0,
      pingIntervalMs: 15_000,
      maxPoints: 3,
    }),
  );

const deliver = async (socket: FakeSocket, payload: unknown): Promise<void> => {
  await act(async () => {
    socket.message(payload);
  });
};

describe("reconnectDelayMs", () => {
  it("doubles per attempt, caps at maxMs and adds bounded jitter", () => {
    const options = { baseMs: 1000, maxMs: 30_000, jitterMs: 500 };
    expect(reconnectDelayMs(0, options, () => 0)).toBe(1000);
    expect(reconnectDelayMs(3, options, () => 0)).toBe(8000);
    expect(reconnectDelayMs(10, options, () => 0)).toBe(30_000);
    expect(reconnectDelayMs(0, options, () => 0.5)).toBe(1250);
  });
});

describe("telemetrySocketUrl", () => {
  it("derives the socket scheme from the page scheme", () => {
    expect(telemetrySocketUrl({ protocol: "http:", host: "localhost:3000" })).toBe("ws://localhost:3000/ws/telemetry");
    expect(telemetrySocketUrl({ protocol: "https:", host: "netpulse.example" })).toBe(
      "wss://netpulse.example/ws/telemetry",
    );
  });
});

describe("useTelemetrySocket", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    FakeSocket.reset();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("connects, then writes kpis frames into the summary cache and the port history", async () => {
    const { result, queryClient } = renderSocket();
    expect(FakeSocket.instances).toHaveLength(1);
    expect(FakeSocket.at(0).url).toBe("ws://test/ws/telemetry");
    expect(result.current.status).toBe("connecting");

    act(() => FakeSocket.at(0).open());
    expect(result.current.status).toBe("open");

    await deliver(FakeSocket.at(0), { type: "hello", version: "0.3.0" });
    expect(queryClient.getQueryData(queryKeys.kpiSummary)).toBeUndefined();

    await deliver(FakeSocket.at(0), makeKpiFrame([makePort({ rx_bps: 10 })], "2026-10-26T10:00:00Z"));
    await deliver(FakeSocket.at(0), makeKpiFrame([makePort({ rx_bps: 20, computed_at: "2026-10-26T10:00:05Z" })]));

    expect(queryClient.getQueryData<KpiSnapshot>(queryKeys.kpiSummary)?.summary.rx_bps).toBe(20);
    expect(result.current.history.get("1:1")?.map((point) => point.rx_bps)).toEqual([10, 20]);
  });

  it("ignores malformed messages", async () => {
    const { result, queryClient } = renderSocket();
    act(() => FakeSocket.at(0).open());
    act(() => FakeSocket.at(0).onmessage?.(new MessageEvent("message", { data: "{not json" })));
    await deliver(FakeSocket.at(0), { type: "mystery" });

    expect(queryClient.getQueryCache().getAll()).toHaveLength(0);
    expect(result.current.status).toBe("open");
  });

  it("reconnects with exponential backoff and resets the attempt on open", () => {
    const { result } = renderSocket();
    act(() => FakeSocket.at(0).open());
    act(() => FakeSocket.at(0).serverClose(1013));

    expect(result.current.status).toBe("reconnecting");
    expect(result.current.attempt).toBe(1);

    act(() => vi.advanceTimersByTime(999));
    expect(FakeSocket.instances).toHaveLength(1);
    act(() => vi.advanceTimersByTime(1));
    expect(FakeSocket.instances).toHaveLength(2);

    act(() => FakeSocket.at(1).serverClose());
    expect(result.current.attempt).toBe(2);
    act(() => vi.advanceTimersByTime(1999));
    expect(FakeSocket.instances).toHaveLength(2);
    act(() => vi.advanceTimersByTime(1));
    expect(FakeSocket.instances).toHaveLength(3);

    act(() => FakeSocket.at(2).serverClose());
    act(() => vi.advanceTimersByTime(4000));
    expect(FakeSocket.instances).toHaveLength(4);

    act(() => FakeSocket.at(3).open());
    expect(result.current.status).toBe("open");
    expect(result.current.attempt).toBe(0);
  });

  it("flags store unavailability and records heartbeats", async () => {
    const { result } = renderSocket();
    act(() => FakeSocket.at(0).open());
    await deliver(FakeSocket.at(0), { type: "store_unavailable", at: "2026-10-26T10:00:00Z" });

    expect(result.current.storeUnavailable).toBe(true);
    expect(result.current.lastHeartbeatAt).toBe("2026-10-26T10:00:00Z");

    await deliver(FakeSocket.at(0), { type: "heartbeat", at: "2026-10-26T10:00:05Z" });
    expect(result.current.lastHeartbeatAt).toBe("2026-10-26T10:00:05Z");

    await deliver(FakeSocket.at(0), makeKpiFrame([makePort()]));
    expect(result.current.storeUnavailable).toBe(false);
  });

  it("replaces the open alerts on the first frame, upserts after, and resyncs on reconnect", async () => {
    const { result, queryClient } = renderSocket();
    const openIds = () =>
      (queryClient.getQueryData<AlertList>(queryKeys.alerts("open"))?.alerts ?? []).map((alert) => alert.id);
    queryClient.setQueryData(queryKeys.alerts("open"), {
      generated_at: "2026-10-26T09:59:00Z",
      alerts: [makeAlert({ id: 7 })],
    });
    act(() => FakeSocket.at(0).open());
    expect(result.current.alertsSynced).toBe(false);

    await deliver(
      FakeSocket.at(0),
      makeAlertsFrame([makeAlert({ id: 1 }), makeAlert({ id: 2, opened_at: "2026-10-26T10:01:00Z" })]),
    );
    expect(result.current.alertsSynced).toBe(true);
    expect(openIds()).toEqual([2, 1]);

    await deliver(FakeSocket.at(0), makeAlertsFrame([makeAlert({ id: 1, severity: "critical" })]));
    expect(
      queryClient.getQueryData<AlertList>(queryKeys.alerts("open"))?.alerts.map((alert) => alert.severity),
    ).toEqual(["warning", "critical"]);

    act(() => FakeSocket.at(0).serverClose());
    expect(result.current.alertsSynced).toBe(false);
    expect(openIds()).toEqual([2, 1]);

    act(() => vi.advanceTimersByTime(1000));
    act(() => FakeSocket.at(1).open());
    await deliver(FakeSocket.at(1), makeAlertsFrame([makeAlert({ id: 3 })]));
    expect(openIds()).toEqual([3]);
    expect(result.current.alertsSynced).toBe(true);
  });

  it("pings while open and stops after the socket closes", () => {
    renderSocket();
    act(() => FakeSocket.at(0).open());
    act(() => vi.advanceTimersByTime(15_000));
    expect(FakeSocket.at(0).sent).toEqual(["ping"]);

    act(() => FakeSocket.at(0).serverClose());
    act(() => vi.advanceTimersByTime(15_000));
    expect(FakeSocket.at(0).sent).toEqual(["ping"]);
  });

  it("closes the socket and cancels reconnects on unmount", () => {
    const { unmount } = renderSocket();
    act(() => FakeSocket.at(0).open());
    act(() => FakeSocket.at(0).serverClose());
    unmount();

    act(() => vi.advanceTimersByTime(60_000));
    expect(FakeSocket.instances).toHaveLength(1);
    expect(FakeSocket.at(0).closedByClient).toBe(true);
  });
});
