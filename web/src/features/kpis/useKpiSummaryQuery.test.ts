import { act, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ApiError } from "../../api/client";
import { queryKeys } from "../../api/keys";
import { createFakeApiClient } from "../../test/fakeApiClient";
import { renderHookWithProviders } from "../../test/renderWithProviders";
import { makePort, makeSnapshot } from "../telemetry/fixtures";
import { useKpiSummaryQuery } from "./useKpiSummaryQuery";

describe("useKpiSummaryQuery", () => {
  it("is null until the REST summary arrives", async () => {
    const snapshot = makeSnapshot([makePort()]);
    const apiClient = createFakeApiClient({ getKpiSummary: () => Promise.resolve(snapshot) });
    const { result } = renderHookWithProviders(() => useKpiSummaryQuery(), { apiClient });

    expect(result.current).toBeNull();
    await waitFor(() => expect(result.current).toEqual(snapshot));
  });

  it("stays null when the summary cannot be fetched", async () => {
    const apiClient = createFakeApiClient({
      getKpiSummary: () => Promise.reject(new ApiError("unavailable", "down", 503)),
    });
    const { result } = renderHookWithProviders(() => useKpiSummaryQuery(), { apiClient });

    await waitFor(() => expect(apiClient.getKpiSummary).toHaveBeenCalled());
    expect(result.current).toBeNull();
  });

  it("follows snapshots written into the cache by another source", async () => {
    const live = makeSnapshot([makePort({ rx_bps: 3_000_000 })], "2026-10-26T10:00:05Z");
    const { result, queryClient } = renderHookWithProviders(() => useKpiSummaryQuery());
    await waitFor(() => expect(result.current).not.toBeNull());

    act(() => {
      queryClient.setQueryData(queryKeys.kpiSummary, live);
    });

    await waitFor(() => expect(result.current).toEqual(live));
  });
});
