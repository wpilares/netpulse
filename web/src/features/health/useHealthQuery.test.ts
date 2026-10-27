import { waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ApiError } from "../../api/client";
import { createFakeApiClient } from "../../test/fakeApiClient";
import { renderHookWithProviders } from "../../test/renderWithProviders";
import { useHealthQuery } from "./useHealthQuery";

const report = { status: "ok", database: "disabled", version: "1.0.0" } as const;

describe("useHealthQuery", () => {
  it("is loading first, then online with the report", async () => {
    const apiClient = createFakeApiClient({ getHealth: () => Promise.resolve(report) });
    const { result } = renderHookWithProviders(() => useHealthQuery(60_000), { apiClient });

    expect(result.current).toEqual({ kind: "loading" });
    await waitFor(() => expect(result.current).toEqual({ kind: "online", report }));
    expect(apiClient.getHealth).toHaveBeenCalledWith(expect.any(AbortSignal));
  });

  it("reports the API as offline when the request fails", async () => {
    const apiClient = createFakeApiClient({ getHealth: () => Promise.reject(new ApiError("network", "down")) });
    const { result } = renderHookWithProviders(() => useHealthQuery(60_000), { apiClient });

    await waitFor(() => expect(result.current).toEqual({ kind: "offline" }));
  });

  it("polls the health endpoint at the given interval", async () => {
    const apiClient = createFakeApiClient({ getHealth: () => Promise.resolve(report) });
    renderHookWithProviders(() => useHealthQuery(20), { apiClient });

    await waitFor(() => expect(apiClient.getHealth.mock.calls.length).toBeGreaterThanOrEqual(2));
  });
});
