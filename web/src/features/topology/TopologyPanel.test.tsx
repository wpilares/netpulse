import { fireEvent, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ApiError } from "../../api/client";
import { createFakeApiClient } from "../../test/fakeApiClient";
import { renderWithProviders } from "../../test/renderWithProviders";
import { makeTopology } from "./fixtures";
import { TopologyPanel } from "./TopologyPanel";

describe("TopologyPanel", () => {
  it("loads the topology and renders the graph", async () => {
    const apiClient = createFakeApiClient({ getTopology: () => Promise.resolve(makeTopology()) });
    renderWithProviders(<TopologyPanel />, { apiClient });

    expect(screen.getByText(/Loading topology/)).toBeInTheDocument();
    expect(await screen.findByRole("img", { name: "Network topology: 1 switch, 1 host" })).toBeInTheDocument();
  });

  it("retries the request from the error state", async () => {
    let calls = 0;
    const apiClient = createFakeApiClient({
      getTopology: () => {
        calls += 1;
        return calls === 1 ? Promise.reject(new ApiError("unavailable", "down", 503)) : Promise.resolve(makeTopology());
      },
    });
    renderWithProviders(<TopologyPanel />, { apiClient });

    fireEvent.click(await screen.findByRole("button", { name: "Retry" }));

    expect(await screen.findByRole("img", { name: /Network topology/ })).toBeInTheDocument();
    expect(calls).toBe(2);
  });
});
