import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ApiError } from "../../api/client";
import { createFakeApiClient } from "../../test/fakeApiClient";
import { renderWithProviders } from "../../test/renderWithProviders";
import { ApiHealthStatus } from "./ApiHealthStatus";

describe("ApiHealthStatus", () => {
  it("loads the API health and renders it", async () => {
    const apiClient = createFakeApiClient({
      getHealth: () => Promise.resolve({ status: "ok", database: "up", version: "0.1.0" }),
    });

    renderWithProviders(<ApiHealthStatus pollIntervalMs={60_000} />, { apiClient });

    expect(screen.getByRole("status")).toHaveTextContent("Checking API");
    expect(await screen.findByText(/API online/)).toBeInTheDocument();
  });

  it("renders the offline state when the API cannot be reached", async () => {
    const apiClient = createFakeApiClient({ getHealth: () => Promise.reject(new ApiError("network", "unreachable")) });

    renderWithProviders(<ApiHealthStatus pollIntervalMs={60_000} />, { apiClient });

    expect(await screen.findByText(/API offline/)).toBeInTheDocument();
  });
});
