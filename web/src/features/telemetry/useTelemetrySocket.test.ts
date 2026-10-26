import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createFakeSocket, FakeSocket } from "./fakeSocket";
import { makeKpiFrame, makePort } from "./fixtures";
import { reconnectDelayMs, telemetrySocketUrl, useTelemetrySocket } from "./useTelemetrySocket";

const backoff = { baseMs: 1000, maxMs: 4000, jitterMs: 0 };

const renderSocket = () =>
  renderHook(() =>
    useTelemetrySocket({
      url: "ws://test/ws/telemetry",
      createSocket: createFakeSocket,
      backoff,
      random: () => 0,
      pingIntervalMs: 15_000,
      maxPoints: 3,
    }),
  );

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

  it("connects, then applies kpis frames to latest and history", () => {
    const { result } = renderSocket();
    expect(FakeSocket.instances).toHaveLength(1);
    expect(FakeSocket.at(0).url).toBe("ws://test/ws/telemetry");
    expect(result.current.status).toBe("connecting");

    act(() => FakeSocket.at(0).open());
    expect(result.current.status).toBe("open");

    act(() => FakeSocket.at(0).message({ type: "hello", version: "0.3.0" }));
    expect(result.current.latest).toBeNull();

    act(() => FakeSocket.at(0).message(makeKpiFrame([makePort({ rx_bps: 10 })], "2026-10-26T10:00:00Z")));
    act(() => FakeSocket.at(0).message(makeKpiFrame([makePort({ rx_bps: 20, computed_at: "2026-10-26T10:00:05Z" })])));

    expect(result.current.latest?.summary.rx_bps).toBe(20);
    expect(result.current.history.get("1:1")?.map((point) => point.rx_bps)).toEqual([10, 20]);
  });

  it("ignores malformed messages", () => {
    const { result } = renderSocket();
    act(() => FakeSocket.at(0).open());
    act(() => FakeSocket.at(0).onmessage?.(new MessageEvent("message", { data: "{not json" })));
    act(() => FakeSocket.at(0).message({ type: "mystery" }));

    expect(result.current.latest).toBeNull();
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

  it("flags store unavailability and records heartbeats", () => {
    const { result } = renderSocket();
    act(() => FakeSocket.at(0).open());
    act(() => FakeSocket.at(0).message({ type: "store_unavailable", at: "2026-10-26T10:00:00Z" }));

    expect(result.current.storeUnavailable).toBe(true);
    expect(result.current.lastHeartbeatAt).toBe("2026-10-26T10:00:00Z");

    act(() => FakeSocket.at(0).message({ type: "heartbeat", at: "2026-10-26T10:00:05Z" }));
    expect(result.current.lastHeartbeatAt).toBe("2026-10-26T10:00:05Z");

    act(() => FakeSocket.at(0).message(makeKpiFrame([makePort()])));
    expect(result.current.storeUnavailable).toBe(false);
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
