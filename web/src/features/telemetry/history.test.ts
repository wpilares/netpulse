import { describe, expect, it } from "vitest";
import { makePort, makeSnapshot } from "./fixtures";
import { appendHistory, emptyHistory, portKey } from "./history";

const at = (second: number): string => `2026-10-26T10:00:${String(second).padStart(2, "0")}Z`;

describe("portKey", () => {
  it("joins dpid and port number", () => {
    expect(portKey(3, 12)).toBe("3:12");
  });
});

describe("appendHistory", () => {
  it("keeps points per port in arrival order", () => {
    const first = appendHistory(emptyHistory, makeSnapshot([makePort({ computed_at: at(0), rx_bps: 1 })]), 10);
    const second = appendHistory(first, makeSnapshot([makePort({ computed_at: at(5), rx_bps: 2 })]), 10);

    expect(second.get("1:1")?.map((point) => point.rx_bps)).toEqual([1, 2]);
    expect(first.get("1:1")).toHaveLength(1);
  });

  it("caps each port at maxPoints, dropping the oldest", () => {
    let history = emptyHistory;
    for (let second = 0; second < 5; second += 1) {
      history = appendHistory(history, makeSnapshot([makePort({ computed_at: at(second), rx_bps: second })]), 3);
    }

    expect(history.get("1:1")?.map((point) => point.rx_bps)).toEqual([2, 3, 4]);
  });

  it("tracks multiple ports across switches independently", () => {
    const history = appendHistory(
      emptyHistory,
      makeSnapshot([
        makePort({ dpid: 1, port_no: 1 }),
        makePort({ dpid: 1, port_no: 2 }),
        makePort({ dpid: 2, port_no: 1 }),
      ]),
      10,
    );

    expect([...history.keys()].sort()).toEqual(["1:1", "1:2", "2:1"]);
    expect(history.get("2:1")?.[0]?.dpid).toBe(2);
  });

  it("ignores a point already recorded for the same computed_at", () => {
    const snapshot = makeSnapshot([makePort({ computed_at: at(0) })]);
    const history = appendHistory(appendHistory(emptyHistory, snapshot, 10), snapshot, 10);

    expect(history.get("1:1")).toHaveLength(1);
  });
});
