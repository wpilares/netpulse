import { describe, expect, it, vi } from "vitest";
import { fetchApiHealth, parseApiHealth } from "./health";

describe("parseApiHealth", () => {
  it("accepts a healthy payload", () => {
    expect(parseApiHealth({ status: "ok", database: "up", version: "0.1.0" })).toEqual({
      status: "ok",
      database: "up",
      version: "0.1.0",
    });
  });

  it("accepts a degraded payload", () => {
    expect(parseApiHealth({ status: "degraded", database: "down", version: "0.1.0" })).toEqual({
      status: "degraded",
      database: "down",
      version: "0.1.0",
    });
  });

  it.each([
    null,
    "ok",
    { status: "unknown", database: "up", version: "0.1.0" },
    { status: "ok", database: "sideways", version: "0.1.0" },
    { status: "ok", database: "up" },
  ])("rejects malformed payload %j", (payload) => {
    expect(parseApiHealth(payload)).toBeNull();
  });
});

describe("fetchApiHealth", () => {
  it("returns the parsed health report", async () => {
    const fetcher = vi
      .fn<typeof fetch>()
      .mockResolvedValue(Response.json({ status: "ok", database: "disabled", version: "0.1.0" }));

    await expect(fetchApiHealth(fetcher)).resolves.toEqual({
      kind: "online",
      report: { status: "ok", database: "disabled", version: "0.1.0" },
    });
    expect(fetcher).toHaveBeenCalledWith(
      "/health",
      expect.objectContaining({ headers: { Accept: "application/json" } }),
    );
  });

  it("reads degraded reports returned with a 503 status", async () => {
    const fetcher = vi
      .fn<typeof fetch>()
      .mockResolvedValue(Response.json({ status: "degraded", database: "down", version: "0.1.0" }, { status: 503 }));

    await expect(fetchApiHealth(fetcher)).resolves.toEqual({
      kind: "online",
      report: { status: "degraded", database: "down", version: "0.1.0" },
    });
  });

  it("reports the API as offline when the request fails", async () => {
    const fetcher = vi.fn<typeof fetch>().mockRejectedValue(new TypeError("network down"));

    await expect(fetchApiHealth(fetcher)).resolves.toEqual({ kind: "offline" });
  });

  it("reports the API as offline when the payload is invalid", async () => {
    const fetcher = vi.fn<typeof fetch>().mockResolvedValue(Response.json({ hello: "world" }));

    await expect(fetchApiHealth(fetcher)).resolves.toEqual({ kind: "offline" });
  });
});
