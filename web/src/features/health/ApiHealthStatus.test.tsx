import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ApiHealthStatus } from "./ApiHealthStatus";

describe("ApiHealthStatus", () => {
  it("loads the API health and renders it", async () => {
    const fetcher = vi
      .fn<typeof fetch>()
      .mockResolvedValue(Response.json({ status: "ok", database: "up", version: "0.1.0" }));

    render(<ApiHealthStatus fetcher={fetcher} pollIntervalMs={60_000} />);

    expect(screen.getByRole("status")).toHaveTextContent("Checking API");
    expect(await screen.findByText(/API online/)).toBeInTheDocument();
  });

  it("renders the offline state when the API cannot be reached", async () => {
    const fetcher = vi.fn<typeof fetch>().mockRejectedValue(new TypeError("unreachable"));

    render(<ApiHealthStatus fetcher={fetcher} pollIntervalMs={60_000} />);

    expect(await screen.findByText(/API offline/)).toBeInTheDocument();
  });
});
