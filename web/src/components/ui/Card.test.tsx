import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Card, CardBody, CardHeader, CardTitle } from "./Card";

describe("Card", () => {
  it("renders a labelled section with header and body", () => {
    render(
      <Card aria-labelledby="alerts-title">
        <CardHeader>
          <CardTitle id="alerts-title">Alerts</CardTitle>
        </CardHeader>
        <CardBody>No alerts</CardBody>
      </Card>,
    );

    const region = screen.getByRole("region", { name: "Alerts" });
    expect(region).toHaveTextContent("No alerts");
    expect(screen.getByRole("heading", { level: 2, name: "Alerts" })).toBeInTheDocument();
  });

  it("renders a level-3 title when asked", () => {
    render(<CardTitle level={3}>Ports</CardTitle>);

    expect(screen.getByRole("heading", { level: 3, name: "Ports" })).toBeInTheDocument();
  });

  it("renders header actions beside the title", () => {
    render(
      <CardHeader actions={<button type="button">Refresh</button>}>
        <CardTitle>Topology</CardTitle>
      </CardHeader>,
    );

    expect(screen.getByRole("button", { name: "Refresh" })).toBeInTheDocument();
  });
});
