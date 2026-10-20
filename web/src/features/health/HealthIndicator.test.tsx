import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { HealthIndicator } from "./HealthIndicator";

describe("HealthIndicator", () => {
  it("announces that the API is being checked", () => {
    render(<HealthIndicator health={{ kind: "loading" }} />);

    expect(screen.getByRole("status")).toHaveTextContent("Checking API");
  });

  it("shows the API as offline", () => {
    render(<HealthIndicator health={{ kind: "offline" }} />);

    expect(screen.getByRole("status")).toHaveTextContent("API offline");
    expect(screen.getByRole("status")).toHaveAttribute("data-tone", "critical");
  });

  it("shows a healthy API with its database state and version", () => {
    render(<HealthIndicator health={{ kind: "online", report: { status: "ok", database: "up", version: "0.1.0" } }} />);

    expect(screen.getByRole("status")).toHaveTextContent("API online");
    expect(screen.getByRole("status")).toHaveTextContent("database up");
    expect(screen.getByRole("status")).toHaveTextContent("v0.1.0");
    expect(screen.getByRole("status")).toHaveAttribute("data-tone", "positive");
  });

  it("flags a degraded API", () => {
    render(
      <HealthIndicator
        health={{ kind: "online", report: { status: "degraded", database: "down", version: "0.1.0" } }}
      />,
    );

    expect(screen.getByRole("status")).toHaveTextContent("API degraded");
    expect(screen.getByRole("status")).toHaveAttribute("data-tone", "warning");
  });
});
