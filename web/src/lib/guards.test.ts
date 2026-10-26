import { describe, expect, it } from "vitest";
import { isArrayOf, isNullableNumber, isOneOf, isRecord } from "./guards";

describe("guards", () => {
  it("recognizes plain records", () => {
    expect(isRecord({})).toBe(true);
    expect(isRecord([])).toBe(true);
    expect(isRecord(null)).toBe(false);
    expect(isRecord("text")).toBe(false);
  });

  it("matches string literal options", () => {
    expect(isOneOf(["a", "b"] as const, "a")).toBe(true);
    expect(isOneOf(["a", "b"] as const, "c")).toBe(false);
    expect(isOneOf(["a", "b"] as const, 1)).toBe(false);
  });

  it("accepts numbers and null as nullable numbers", () => {
    expect(isNullableNumber(1.5)).toBe(true);
    expect(isNullableNumber(null)).toBe(true);
    expect(isNullableNumber(undefined)).toBe(false);
    expect(isNullableNumber("1")).toBe(false);
  });

  it("checks every array item with the guard", () => {
    const isString = (value: unknown): value is string => typeof value === "string";
    expect(isArrayOf(["a", "b"], isString)).toBe(true);
    expect(isArrayOf(["a", 1], isString)).toBe(false);
    expect(isArrayOf("ab", isString)).toBe(false);
  });
});
