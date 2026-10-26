import { act, renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { makeAlert } from "./fixtures";
import { type LiveAlerts, useAlerts } from "./useAlerts";

const generatedAt = "2026-10-26T10:00:05Z";
const ackedAt = "2026-10-26T10:03:00Z";

const live = (alerts: LiveAlerts["alerts"], alertsSynced: boolean): LiveAlerts => ({ alerts, alertsSynced });

const requestUrl = (input: string | URL | Request): string =>
  typeof input === "string" ? input : input instanceof URL ? input.href : input.url;

const listResponse = (alerts: readonly ReturnType<typeof makeAlert>[]) =>
  Response.json({ generated_at: generatedAt, alerts });

const renderAlerts = (fetcher: typeof fetch, initial: LiveAlerts = live([], false)) =>
  renderHook(({ current }) => useAlerts(fetcher, current, () => "2026-10-26T10:02:30Z"), {
    initialProps: { current: initial },
  });

describe("useAlerts", () => {
  it("shows the REST alerts until the socket delivers its first snapshot", async () => {
    const fetcher = vi.fn<typeof fetch>(() => Promise.resolve(listResponse([makeAlert({ id: 1 })])));
    const { result, rerender } = renderAlerts(fetcher);

    await waitFor(() => expect(result.current.alerts.map((alert) => alert.id)).toEqual([1]));
    expect(fetcher).toHaveBeenCalledWith("/api/v1/alerts?status=open&limit=100", expect.anything());

    rerender({ current: live([makeAlert({ id: 2, severity: "critical" })], true) });

    expect(result.current.alerts.map((alert) => alert.id)).toEqual([2]);
    expect(result.current.summary).toEqual({ open: 1, critical: 1, warning: 0, acknowledged: 0 });
    expect(result.current.error).toBeNull();
  });

  it("hides resolved alerts delivered by the socket", () => {
    const fetcher = vi.fn<typeof fetch>(() => Promise.resolve(listResponse([])));
    const resolved = makeAlert({ id: 3, status: "resolved", resolved_at: ackedAt });
    const { result } = renderAlerts(fetcher, live([resolved, makeAlert({ id: 4 })], true));

    expect(result.current.alerts.map((alert) => alert.id)).toEqual([4]);
  });

  it("reports an error when the alerts API is unavailable", async () => {
    const fetcher = vi.fn<typeof fetch>(() => Promise.resolve(new Response(null, { status: 503 })));
    const { result } = renderAlerts(fetcher);

    await waitFor(() => expect(result.current.error).toBe("Alert storage unavailable"));
    expect(result.current.alerts).toEqual([]);
  });

  it("acknowledges optimistically, then keeps the server timestamp", async () => {
    let respond: (response: Response) => void = () => undefined;
    const fetcher = vi.fn<typeof fetch>((input) =>
      requestUrl(input).endsWith("/ack")
        ? new Promise<Response>((resolve) => {
            respond = resolve;
          })
        : Promise.resolve(listResponse([makeAlert({ id: 1 })])),
    );
    const { result } = renderAlerts(fetcher);
    await waitFor(() => expect(result.current.alerts).toHaveLength(1));

    act(() => {
      void result.current.acknowledge(1);
    });

    expect(result.current.pending.has(1)).toBe(true);
    expect(result.current.alerts[0]?.acknowledged_at).toBe("2026-10-26T10:02:30Z");
    expect(result.current.summary.acknowledged).toBe(1);

    await act(async () => {
      respond(Response.json(makeAlert({ id: 1, acknowledged_at: ackedAt })));
    });

    expect(fetcher).toHaveBeenCalledWith("/api/v1/alerts/1/ack", expect.objectContaining({ method: "POST" }));
    expect(result.current.pending.size).toBe(0);
    expect(result.current.alerts[0]?.acknowledged_at).toBe(ackedAt);
  });

  it("rolls back the optimistic acknowledgement when the request fails", async () => {
    const fetcher = vi.fn<typeof fetch>((input) =>
      Promise.resolve(
        requestUrl(input).endsWith("/ack") ? new Response(null, { status: 404 }) : listResponse([makeAlert({ id: 1 })]),
      ),
    );
    const { result } = renderAlerts(fetcher);
    await waitFor(() => expect(result.current.alerts).toHaveLength(1));

    await act(async () => {
      await result.current.acknowledge(1);
    });

    expect(result.current.alerts[0]?.acknowledged_at).toBeNull();
    expect(result.current.pending.size).toBe(0);
    expect(result.current.error).toBe("Alert not found");
  });

  it("loads resolved alerts on demand and hides them again", async () => {
    const resolved = makeAlert({ id: 9, status: "resolved", resolved_at: ackedAt });
    const fetcher = vi.fn<typeof fetch>((input) =>
      Promise.resolve(requestUrl(input).includes("status=resolved") ? listResponse([resolved]) : listResponse([])),
    );
    const { result } = renderAlerts(fetcher, live([], true));

    expect(result.current.resolved).toEqual({ kind: "hidden" });

    act(() => result.current.toggleResolved());
    expect(result.current.resolved).toEqual({ kind: "loading" });

    await waitFor(() => expect(result.current.resolved).toEqual({ kind: "ready", alerts: [resolved] }));
    expect(fetcher).toHaveBeenCalledWith("/api/v1/alerts?status=resolved&limit=50", expect.anything());

    act(() => result.current.toggleResolved());
    expect(result.current.resolved).toEqual({ kind: "hidden" });
  });

  it("explains when resolved alerts cannot be loaded", async () => {
    const fetcher = vi.fn<typeof fetch>((input) =>
      Promise.resolve(
        requestUrl(input).includes("status=resolved") ? new Response(null, { status: 503 }) : listResponse([]),
      ),
    );
    const { result } = renderAlerts(fetcher, live([], true));

    act(() => result.current.toggleResolved());

    await waitFor(() =>
      expect(result.current.resolved).toEqual({ kind: "unavailable", reason: "Alert storage unavailable" }),
    );
  });
});
