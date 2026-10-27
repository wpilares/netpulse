import { act, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ApiError } from "../../api/client";
import { queryKeys } from "../../api/keys";
import type { AlertList } from "../../api/schemas";
import { createFakeApiClient } from "../../test/fakeApiClient";
import { renderHookWithProviders } from "../../test/renderWithProviders";
import { makeAlert } from "./fixtures";
import { useAlertsQuery } from "./useAlertsQuery";

const generatedAt = "2026-10-26T10:00:05Z";
const resolvedAt = "2026-10-26T10:03:00Z";

const list = (alerts: readonly ReturnType<typeof makeAlert>[]): AlertList => ({ generated_at: generatedAt, alerts });

const renderAlerts = (apiClient = createFakeApiClient(), alertsSynced = false) =>
  renderHookWithProviders(({ synced }: { readonly synced: boolean }) => useAlertsQuery({ alertsSynced: synced }), {
    apiClient,
    initialProps: { synced: alertsSynced },
  });

describe("useAlertsQuery", () => {
  it("fetches the open list over REST until the socket is synced, then reads the cache only", async () => {
    const apiClient = createFakeApiClient({ listAlerts: () => Promise.resolve(list([makeAlert({ id: 1 })])) });
    const { result, rerender, queryClient } = renderAlerts(apiClient);

    await waitFor(() => expect(result.current.alerts.map((alert) => alert.id)).toEqual([1]));
    expect(apiClient.listAlerts).toHaveBeenCalledWith({ status: "open", limit: 100 }, expect.any(AbortSignal));
    expect(result.current.error).toBeNull();

    rerender({ synced: true });
    act(() => {
      queryClient.setQueryData(queryKeys.alerts("open"), list([makeAlert({ id: 2, severity: "critical" })]));
    });

    await waitFor(() => expect(result.current.alerts.map((alert) => alert.id)).toEqual([2]));
    expect(result.current.summary).toEqual({ open: 1, critical: 1, warning: 0, acknowledged: 0 });
    expect(apiClient.listAlerts).toHaveBeenCalledTimes(1);
  });

  it("hides resolved alerts that are still in the cache", async () => {
    const resolved = makeAlert({ id: 3, status: "resolved", resolved_at: resolvedAt });
    const apiClient = createFakeApiClient({
      listAlerts: () => Promise.resolve(list([resolved, makeAlert({ id: 4 })])),
    });
    const { result } = renderAlerts(apiClient);

    await waitFor(() => expect(result.current.alerts.map((alert) => alert.id)).toEqual([4]));
  });

  it("reports an error when the alerts API is unavailable", async () => {
    const apiClient = createFakeApiClient({
      listAlerts: () => Promise.reject(new ApiError("unavailable", "storage down", 503)),
    });
    const { result } = renderAlerts(apiClient);

    await waitFor(() => expect(result.current.error).toBe("Alert storage unavailable"));
    expect(result.current.alerts).toEqual([]);
  });

  it("loads resolved alerts on demand and hides them again", async () => {
    const resolved = makeAlert({ id: 9, status: "resolved", resolved_at: resolvedAt });
    const apiClient = createFakeApiClient({
      listAlerts: ({ status }) => Promise.resolve(status === "resolved" ? list([resolved]) : list([])),
    });
    const { result } = renderAlerts(apiClient, true);

    expect(result.current.resolved).toEqual({ kind: "hidden" });
    expect(apiClient.listAlerts).not.toHaveBeenCalled();

    act(() => result.current.setFilter("resolved"));
    expect(result.current.filter).toBe("resolved");
    expect(result.current.resolved).toEqual({ kind: "loading" });

    await waitFor(() => expect(result.current.resolved).toEqual({ kind: "ready", alerts: [resolved] }));
    expect(apiClient.listAlerts).toHaveBeenCalledWith({ status: "resolved", limit: 50 }, expect.any(AbortSignal));

    act(() => result.current.setFilter("open"));
    expect(result.current.filter).toBe("open");
    expect(result.current.resolved).toEqual({ kind: "hidden" });
  });

  it("explains when resolved alerts cannot be loaded", async () => {
    const apiClient = createFakeApiClient({
      listAlerts: ({ status }) =>
        status === "resolved" ? Promise.reject(new ApiError("unavailable", "down", 503)) : Promise.resolve(list([])),
    });
    const { result } = renderAlerts(apiClient, true);

    act(() => result.current.setFilter("resolved"));

    await waitFor(() =>
      expect(result.current.resolved).toEqual({ kind: "unavailable", reason: "Alert storage unavailable" }),
    );
  });
});
