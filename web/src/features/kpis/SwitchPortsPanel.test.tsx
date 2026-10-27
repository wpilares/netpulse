import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { makePort, makeSnapshot } from "../telemetry/fixtures";
import { appendHistory, emptyHistory } from "../telemetry/history";
import { SwitchPortsPanel } from "./SwitchPortsPanel";

describe("SwitchPortsPanel", () => {
  const snapshot = makeSnapshot([
    makePort({ dpid: 2, port_no: 2 }),
    makePort({ dpid: 2, port_no: 1, counter_reset: true }),
    makePort({ dpid: 1, port_no: 1 }),
  ]);
  const history = appendHistory(emptyHistory, snapshot, 10);

  it("selects the lowest switch by default and lists its ports in order", () => {
    render(<SwitchPortsPanel latest={snapshot} history={history} />);

    expect(screen.getByRole("region", { name: "Switch ports" })).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: "Switch 1" })).toBeChecked();
    expect(screen.getAllByRole("heading", { level: 3 }).map((heading) => heading.textContent)).toEqual(["Port 1"]);
  });

  it("switches the port list and highlights counter resets", () => {
    render(<SwitchPortsPanel latest={snapshot} history={history} />);

    fireEvent.click(screen.getByRole("radio", { name: "Switch 2" }));

    expect(screen.getByRole("radio", { name: "Switch 2" })).toBeChecked();
    expect(screen.getAllByRole("heading", { level: 3 }).map((heading) => heading.textContent)).toEqual([
      "Port 1",
      "Port 2",
    ]);
    expect(screen.getByText("Counter reset")).toHaveAttribute("data-tone", "warning");
    expect(screen.getByRole("region", { name: "Port 1" })).toHaveAttribute("data-reset", "true");
    expect(screen.getByRole("region", { name: "Port 2" })).toHaveAttribute("data-reset", "false");
  });

  it("explains when no switch is reporting", () => {
    render(<SwitchPortsPanel latest={null} history={emptyHistory} />);

    expect(screen.getByText("No switches reporting yet")).toBeInTheDocument();
    expect(screen.queryByRole("radiogroup")).not.toBeInTheDocument();
  });
});
