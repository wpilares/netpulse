import { describe, expect, it, vi } from "vitest";
import { makePort, makeSnapshot } from "../telemetry/fixtures";
import { fetchKpiSummary } from "./summary";

describe("fetchKpiSummary", () => {
  it("returns the parsed snapshot", async () => {
    const snapshot = makeSnapshot([makePort()]);
    const fetcher = vi.fn<typeof fetch>().mockResolvedValue(Response.json(snapshot));

    await expect(fetchKpiSummary(fetcher)).resolves.toEqual(snapshot);
    expect(fetcher).toHaveBeenCalledWith(
      "/api/v1/kpis/summary",
      expect.objectContaining({ headers: { Accept: "application/json" } }),
    );
  });

  it("returns null on failure or malformed payloads", async () => {
    await expect(
      fetchKpiSummary(vi.fn<typeof fetch>().mockRejectedValue(new TypeError("offline"))),
    ).resolves.toBeNull();
    await expect(
      fetchKpiSummary(vi.fn<typeof fetch>().mockResolvedValue(Response.json({ nope: 1 }))),
    ).resolves.toBeNull();
  });
});
