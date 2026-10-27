import { describe, expect, it, vi } from "vitest";
import { makeAlert } from "../features/alerts/fixtures";
import { makePort, makeSnapshot } from "../features/telemetry/fixtures";
import { makeTopology } from "../features/topology/fixtures";
import { ApiError, createApiClient, type FetchImpl } from "./client";

const BASE_URL = "http://netpulse.test";

interface SeenRequest {
  readonly method: string;
  readonly path: string;
  readonly accept: string | null;
}

const toRequest = (input: URL | Request | string, init?: RequestInit): Request =>
  input instanceof Request ? input : new Request(input, init);

const describeRequest = (request: Request): SeenRequest => {
  const url = new URL(request.url);
  return { method: request.method, path: `${url.pathname}${url.search}`, accept: request.headers.get("accept") };
};

const fetchWith = (respond: (seen: SeenRequest) => Response | Promise<Response>) => {
  const seen: SeenRequest[] = [];
  const fetchImpl = vi.fn<FetchImpl>((input, init) => {
    const request = describeRequest(toRequest(input, init));
    seen.push(request);
    return Promise.resolve(respond(request));
  });
  return { fetchImpl, seen };
};

const json = (body: unknown, status = 200): Response => Response.json(body, { status });

const pendUntilAborted: FetchImpl = (input, init) =>
  new Promise<Response>((_resolve, reject) => {
    const request = toRequest(input, init);
    request.signal.addEventListener("abort", () => reject(request.signal.reason));
  });

const clientWith = (respond: (seen: SeenRequest) => Response | Promise<Response>) => {
  const { fetchImpl, seen } = fetchWith(respond);
  return { client: createApiClient({ baseURL: BASE_URL, fetchImpl }), seen };
};

const rejection = async (promise: Promise<unknown>): Promise<ApiError> => {
  try {
    await promise;
  } catch (error: unknown) {
    if (error instanceof ApiError) {
      return error;
    }
    throw new Error(`expected an ApiError, got ${String(error)}`);
  }
  throw new Error("expected the request to reject");
};

describe("createApiClient", () => {
  it("reads the health report with a JSON accept header", async () => {
    const { client, seen } = clientWith(() => json({ status: "ok", database: "up", version: "1.0.0" }));

    await expect(client.getHealth()).resolves.toEqual({ status: "ok", database: "up", version: "1.0.0" });
    expect(seen).toEqual([{ method: "GET", path: "/health", accept: "application/json" }]);
  });

  it("still parses the degraded health report returned with a 503", async () => {
    const { client } = clientWith(() => json({ status: "degraded", database: "down", version: "1.0.0" }, 503));

    await expect(client.getHealth()).resolves.toEqual({ status: "degraded", database: "down", version: "1.0.0" });
  });

  it("reads the KPI summary", async () => {
    const snapshot = makeSnapshot([makePort()]);
    const { client, seen } = clientWith(() => json(snapshot));

    await expect(client.getKpiSummary()).resolves.toEqual(snapshot);
    expect(seen[0]?.path).toBe("/api/v1/kpis/summary");
  });

  it("reads the topology", async () => {
    const topology = makeTopology();
    const { client, seen } = clientWith(() => json(topology));

    await expect(client.getTopology()).resolves.toEqual(topology);
    expect(seen[0]?.path).toBe("/api/v1/topology");
  });

  it("lists alerts filtered by status and limit", async () => {
    const list = { generated_at: "2026-10-26T10:00:05Z", alerts: [makeAlert()] };
    const { client, seen } = clientWith(() => json(list));

    await expect(client.listAlerts({ status: "resolved", limit: 50 })).resolves.toEqual(list);
    expect(seen[0]?.path).toBe("/api/v1/alerts?status=resolved&limit=50");
  });

  it("posts an acknowledgement and returns the updated alert", async () => {
    const acked = makeAlert({ id: 7, acknowledged_at: "2026-10-26T10:03:00Z" });
    const { client, seen } = clientWith(() => json(acked));

    await expect(client.acknowledgeAlert(7)).resolves.toEqual(acked);
    expect(seen).toEqual([{ method: "POST", path: "/api/v1/alerts/7/ack", accept: "application/json" }]);
  });

  it("maps a 404 to a not_found error", async () => {
    const { client } = clientWith(() => new Response(null, { status: 404 }));

    const error = await rejection(client.acknowledgeAlert(9));
    expect(error).toMatchObject({ kind: "not_found", status: 404, name: "ApiError" });
  });

  it("maps a 503 to an unavailable error", async () => {
    const { client } = clientWith(() => json({ detail: "storage down" }, 503));

    await expect(rejection(client.listAlerts({ status: "open", limit: 100 }))).resolves.toMatchObject({
      kind: "unavailable",
      status: 503,
    });
  });

  it("maps any other failing status to an unavailable error", async () => {
    const { client } = clientWith(() => new Response(null, { status: 500 }));

    await expect(rejection(client.getTopology())).resolves.toMatchObject({ kind: "unavailable", status: 500 });
  });

  it("maps a failed connection to a network error", async () => {
    const { client } = clientWith(() => Promise.reject(new TypeError("Failed to fetch")));

    await expect(rejection(client.getKpiSummary())).resolves.toMatchObject({ kind: "network", status: undefined });
  });

  it("maps an unexpected body shape to an invalid error", async () => {
    const { client } = clientWith(() => json({ nope: 1 }));

    await expect(rejection(client.getKpiSummary())).resolves.toMatchObject({ kind: "invalid" });
  });

  it("maps a non-JSON body to an invalid error", async () => {
    const { client } = clientWith(() => new Response("<html></html>", { status: 200 }));

    await expect(rejection(client.getHealth())).resolves.toMatchObject({ kind: "invalid" });
  });

  it("rejects with a network error when the caller aborts the request", async () => {
    const pendingFetch = vi.fn<FetchImpl>(pendUntilAborted);
    const client = createApiClient({ baseURL: BASE_URL, fetchImpl: pendingFetch });
    const controller = new AbortController();

    const outcome = rejection(client.getTopology(controller.signal));
    await vi.waitFor(() => expect(pendingFetch).toHaveBeenCalledTimes(1));
    controller.abort();

    await expect(outcome).resolves.toMatchObject({ kind: "network" });
  });

  it("rejects with a network error when the request times out", async () => {
    const client = createApiClient({ baseURL: BASE_URL, fetchImpl: pendUntilAborted, timeoutMs: 10 });

    await expect(rejection(client.getHealth())).resolves.toMatchObject({ kind: "network" });
  });
});
