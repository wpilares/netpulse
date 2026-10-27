import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ChartFrame } from "./ChartFrame";

describe("ChartFrame", () => {
  it("frames a chart with a title, a caption and a legend of series values", () => {
    render(
      <ChartFrame
        title="Throughput"
        caption="10:00:05"
        series={[
          { id: "rx", label: "Receive", value: "2.0 Mb/s", color: "var(--series-rx)" },
          { id: "tx", label: "Transmit", value: "350.0 kb/s", color: "var(--series-tx)" },
        ]}
      >
        <svg role="img" aria-label="Chart" />
      </ChartFrame>,
    );

    expect(screen.getByRole("figure")).toContainElement(screen.getByRole("img", { name: "Chart" }));
    expect(screen.getByText("Throughput")).toBeInTheDocument();
    expect(screen.getByText("10:00:05")).toBeInTheDocument();
    const legend = screen.getByRole("list", { name: "Throughput series" });
    const items = within(legend).getAllByRole("listitem");
    expect(items.map((item) => item.textContent)).toEqual(["Receive2.0 Mb/s", "Transmit350.0 kb/s"]);
    expect(items.map((item) => item.getAttribute("data-series"))).toEqual(["rx", "tx"]);
    expect(items[0]?.querySelector('[aria-hidden="true"]')).not.toBeNull();
  });
});
