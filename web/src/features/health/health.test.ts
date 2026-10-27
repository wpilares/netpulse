import { describe, expect, it } from "vitest";
import { parseApiHealth, toApiHealth } from "./health";

const report = { status: "ok", database: "up", version: "1.0.0" } as const;

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

describe("toApiHealth", () => {
  it("is loading until the first report arrives", () => {
    expect(toApiHealth({ status: "pending", data: undefined })).toEqual({ kind: "loading" });
  });

  it("is online with the report on success", () => {
    expect(toApiHealth({ status: "success", data: report })).toEqual({ kind: "online", report });
  });

  it("is offline when the last poll failed, even with an older report cached", () => {
    expect(toApiHealth({ status: "error", data: report })).toEqual({ kind: "offline" });
    expect(toApiHealth({ status: "error", data: undefined })).toEqual({ kind: "offline" });
  });
});
