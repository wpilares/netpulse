import { describe, expect, it, vi } from "vitest";
import {
  acknowledgeAlert,
  alertSummary,
  describeAlert,
  describeAlertError,
  fetchAlerts,
  openAlerts,
  parseAlert,
  parseAlertList,
  upsertAlerts,
} from "./alerts";
import { makeAlert } from "./fixtures";

const generatedAt = "2026-10-26T10:00:05Z";

const respondWith = (body: unknown, status = 200) =>
  vi.fn<typeof fetch>(() => Promise.resolve(status === 200 ? Response.json(body) : new Response(null, { status })));

describe("parseAlert", () => {
  it("parses a full alert payload", () => {
    const alert = makeAlert({ acknowledged_at: "2026-10-26T10:01:00Z", resolved_at: "2026-10-26T10:02:00Z" });
    expect(parseAlert({ ...alert })).toEqual(alert);
  });

  it.each([
    null,
    { ...makeAlert(), metric: "latency" },
    { ...makeAlert(), severity: "info" },
    { ...makeAlert(), status: "closed" },
    { ...makeAlert(), resolved_at: 12 },
    { ...makeAlert(), value: "9" },
    { ...makeAlert(), id: "1" },
    { ...makeAlert(), updated_at: undefined },
  ])("rejects malformed alert %j", (payload) => {
    expect(parseAlert(payload)).toBeNull();
  });
});

describe("parseAlertList", () => {
  it("parses the list envelope", () => {
    const list = { generated_at: generatedAt, alerts: [makeAlert(), makeAlert({ id: 2 })] };
    expect(parseAlertList(list)).toEqual(list);
  });

  it("rejects a list with a malformed alert", () => {
    expect(parseAlertList({ generated_at: generatedAt, alerts: [{ id: 1 }] })).toBeNull();
    expect(parseAlertList({ alerts: [] })).toBeNull();
  });
});

describe("fetchAlerts", () => {
  it("requests alerts with the status and limit query", async () => {
    const list = { generated_at: generatedAt, alerts: [makeAlert()] };
    const fetcher = respondWith(list);

    await expect(fetchAlerts(fetcher, { status: "resolved", limit: 50 })).resolves.toEqual(list);
    expect(fetcher).toHaveBeenCalledWith(
      "/api/v1/alerts?status=resolved&limit=50",
      expect.objectContaining({ headers: { Accept: "application/json" } }),
    );
  });

  it("throws an unavailable error when storage is down", async () => {
    await expect(fetchAlerts(respondWith(null, 503), { status: "open", limit: 100 })).rejects.toMatchObject({
      kind: "unavailable",
    });
  });

  it("throws an invalid error on a malformed body", async () => {
    await expect(fetchAlerts(respondWith({ alerts: "none" }), { status: "open", limit: 100 })).rejects.toMatchObject({
      kind: "invalid",
    });
  });

  it("throws an unavailable error when the request itself fails", async () => {
    const fetcher = vi.fn<typeof fetch>(() => Promise.reject(new TypeError("Failed to fetch")));
    await expect(fetchAlerts(fetcher, { status: "open", limit: 100 })).rejects.toMatchObject({ kind: "unavailable" });
  });
});

describe("acknowledgeAlert", () => {
  it("posts the acknowledgement and returns the updated alert", async () => {
    const acked = makeAlert({ id: 7, acknowledged_at: "2026-10-26T10:03:00Z" });
    const fetcher = respondWith(acked);

    await expect(acknowledgeAlert(fetcher, 7)).resolves.toEqual(acked);
    expect(fetcher).toHaveBeenCalledWith("/api/v1/alerts/7/ack", expect.objectContaining({ method: "POST" }));
  });

  it("throws a not found error for an unknown id", async () => {
    await expect(acknowledgeAlert(respondWith(null, 404), 9)).rejects.toMatchObject({ kind: "not_found" });
  });

  it("throws an unavailable error when storage is down", async () => {
    await expect(acknowledgeAlert(respondWith(null, 503), 9)).rejects.toMatchObject({ kind: "unavailable" });
  });
});

describe("describeAlertError", () => {
  it("turns typed failures into user facing text", async () => {
    await expect(acknowledgeAlert(respondWith(null, 404), 9).catch(describeAlertError)).resolves.toBe(
      "Alert not found",
    );
    await expect(
      fetchAlerts(respondWith(null, 503), { status: "open", limit: 1 }).catch(describeAlertError),
    ).resolves.toBe("Alert storage unavailable");
    expect(describeAlertError(new Error("boom"))).toBe("Alerts unavailable");
  });
});

describe("upsertAlerts", () => {
  const older = makeAlert({ id: 1, opened_at: "2026-10-26T10:00:00Z" });
  const newer = makeAlert({ id: 2, opened_at: "2026-10-26T10:02:00Z" });

  it("orders alerts by newest opened first", () => {
    expect(upsertAlerts([], [older, newer]).map((alert) => alert.id)).toEqual([2, 1]);
  });

  it("replaces alerts by id and inserts new ones in place", () => {
    const current = upsertAlerts([], [older, newer]);
    const resolved = { ...older, status: "resolved" as const, resolved_at: "2026-10-26T10:05:00Z" };
    const middle = makeAlert({ id: 3, opened_at: "2026-10-26T10:01:00Z" });

    const next = upsertAlerts(current, [resolved, middle]);

    expect(next.map((alert) => [alert.id, alert.status])).toEqual([
      [2, "open"],
      [3, "open"],
      [1, "resolved"],
    ]);
  });

  it("breaks ties on opened_at by the newest id", () => {
    const twin = makeAlert({ id: 5, opened_at: older.opened_at });
    expect(upsertAlerts([older], [twin]).map((alert) => alert.id)).toEqual([5, 1]);
  });
});

describe("openAlerts and alertSummary", () => {
  const alerts = [
    makeAlert({ id: 1, severity: "critical" }),
    makeAlert({ id: 2, acknowledged_at: "2026-10-26T10:01:00Z" }),
    makeAlert({ id: 3, status: "resolved", severity: "critical", resolved_at: "2026-10-26T10:04:00Z" }),
  ];

  it("keeps only open alerts", () => {
    expect(openAlerts(alerts).map((alert) => alert.id)).toEqual([1, 2]);
  });

  it("counts open alerts by severity and acknowledgement", () => {
    expect(alertSummary(alerts)).toEqual({ open: 2, critical: 1, warning: 1, acknowledged: 1 });
    expect(alertSummary([])).toEqual({ open: 0, critical: 0, warning: 0, acknowledged: 0 });
  });
});

describe("describeAlert", () => {
  it("formats throughput alerts in bits per second", () => {
    expect(describeAlert(makeAlert())).toBe("Port 2 on switch 1: rx_bps 9.4 Mb/s, expected 1.2 Mb/s (z 6.5)");
  });

  it("formats rate alerts as percentages", () => {
    const alert = makeAlert({ dpid: 3, port_no: 4, metric: "drop_rate", value: 0.052, expected: 0.001, zscore: -7.2 });
    expect(describeAlert(alert)).toBe("Port 4 on switch 3: drop_rate 5.2%, expected 0.1% (z -7.2)");
  });
});
