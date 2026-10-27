import { act, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ApiError } from "../../api/client";
import { queryKeys } from "../../api/keys";
import type { Alert, AlertList } from "../../api/schemas";
import { createFakeApiClient } from "../../test/fakeApiClient";
import { renderHookWithProviders } from "../../test/renderWithProviders";
import { makeAlert } from "./fixtures";
import { useAcknowledgeAlert } from "./useAcknowledgeAlert";

const optimisticAt = "2026-10-26T10:02:30Z";
const serverAt = "2026-10-26T10:03:00Z";
const openKey = queryKeys.alerts("open");

const list = (alerts: readonly Alert[]): AlertList => ({ generated_at: "2026-10-26T10:00:05Z", alerts });

const renderAck = (apiClient = createFakeApiClient()) => {
  const rendered = renderHookWithProviders(() => useAcknowledgeAlert(() => optimisticAt), { apiClient });
  rendered.queryClient.setQueryData(openKey, list([makeAlert({ id: 1 })]));
  return rendered;
};

const cachedAlert = (queryClient: ReturnType<typeof renderAck>["queryClient"], id: number): Alert | undefined =>
  queryClient.getQueryData<AlertList>(openKey)?.alerts.find((alert) => alert.id === id);

describe("useAcknowledgeAlert", () => {
  it("acknowledges optimistically, then keeps the server timestamp", async () => {
    let respond: (alert: Alert) => void = () => undefined;
    const apiClient = createFakeApiClient({
      acknowledgeAlert: () =>
        new Promise<Alert>((resolve) => {
          respond = resolve;
        }),
    });
    const { result, queryClient } = renderAck(apiClient);

    act(() => {
      void result.current.acknowledge(1);
    });

    await waitFor(() => expect(result.current.pending.has(1)).toBe(true));
    await waitFor(() => expect(cachedAlert(queryClient, 1)?.acknowledged_at).toBe(optimisticAt));

    await act(async () => {
      respond(makeAlert({ id: 1, acknowledged_at: serverAt }));
    });

    expect(apiClient.acknowledgeAlert).toHaveBeenCalledWith(1);
    await waitFor(() => expect(result.current.pending.size).toBe(0));
    expect(cachedAlert(queryClient, 1)?.acknowledged_at).toBe(serverAt);
    expect(result.current.error).toBeNull();
  });

  it("rolls back the optimistic acknowledgement when the request fails", async () => {
    const apiClient = createFakeApiClient({
      acknowledgeAlert: () => Promise.reject(new ApiError("not_found", "missing", 404)),
    });
    const { result, queryClient } = renderAck(apiClient);

    await act(async () => {
      await result.current.acknowledge(1);
    });

    await waitFor(() => expect(result.current.error).toBe("Alert not found"));
    expect(cachedAlert(queryClient, 1)?.acknowledged_at).toBeNull();
    expect(result.current.pending.size).toBe(0);
  });

  it("keeps alerts that arrived while the request was pending when rolling back", async () => {
    let fail: (error: Error) => void = () => undefined;
    const apiClient = createFakeApiClient({
      acknowledgeAlert: () =>
        new Promise<Alert>((_resolve, reject) => {
          fail = reject;
        }),
    });
    const { result, queryClient } = renderAck(apiClient);

    act(() => {
      void result.current.acknowledge(1);
    });
    await waitFor(() => expect(cachedAlert(queryClient, 1)?.acknowledged_at).toBe(optimisticAt));
    act(() => {
      queryClient.setQueryData<AlertList>(openKey, (current) =>
        current === undefined ? current : list([...current.alerts, makeAlert({ id: 2 })]),
      );
    });

    await act(async () => {
      fail(new ApiError("unavailable", "down", 503));
    });

    await waitFor(() => expect(result.current.pending.size).toBe(0));
    expect(cachedAlert(queryClient, 1)?.acknowledged_at).toBeNull();
    expect(cachedAlert(queryClient, 2)).toBeDefined();
    expect(result.current.error).toBe("Alert storage unavailable");
  });
});
