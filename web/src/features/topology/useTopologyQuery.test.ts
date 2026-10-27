import { waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ApiError } from "../../api/client";
import { createFakeApiClient } from "../../test/fakeApiClient";
import { renderHookWithProviders } from "../../test/renderWithProviders";
import { makeTopology } from "./fixtures";
import { useTopologyQuery } from "./useTopologyQuery";

describe("useTopologyQuery", () => {
  it("is loading first, then ready with the topology", async () => {
    const topology = makeTopology();
    const apiClient = createFakeApiClient({ getTopology: () => Promise.resolve(topology) });
    const { result } = renderHookWithProviders(() => useTopologyQuery(60_000), { apiClient });

    expect(result.current).toEqual({ kind: "loading" });
    await waitFor(() => expect(result.current).toEqual({ kind: "ready", topology }));
    expect(apiClient.getTopology).toHaveBeenCalledWith(expect.any(AbortSignal));
  });

  it("reports the controller as unavailable when the request fails", async () => {
    const apiClient = createFakeApiClient({
      getTopology: () => Promise.reject(new ApiError("unavailable", "controller down", 503)),
    });
    const { result } = renderHookWithProviders(() => useTopologyQuery(60_000), { apiClient });

    await waitFor(() => expect(result.current).toEqual({ kind: "unavailable" }));
  });

  it("refreshes the topology at the given interval", async () => {
    const apiClient = createFakeApiClient();
    renderHookWithProviders(() => useTopologyQuery(20), { apiClient });

    await waitFor(() => expect(apiClient.getTopology.mock.calls.length).toBeGreaterThanOrEqual(2));
  });
});
