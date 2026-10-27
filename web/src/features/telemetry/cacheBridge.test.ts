import { describe, expect, it } from "vitest";
import { queryKeys } from "../../api/keys";
import { createQueryClient } from "../../api/queryClient";
import type { AlertList, KpiSnapshot } from "../../api/schemas";
import { makeAlert, makeAlertsFrame } from "../alerts/fixtures";
import { applyLiveFrame } from "./cacheBridge";
import { makeKpiFrame, makePort } from "./fixtures";

const openKey = queryKeys.alerts("open");

const openIds = (queryClient: ReturnType<typeof createQueryClient>): number[] =>
  (queryClient.getQueryData<AlertList>(openKey)?.alerts ?? []).map((alert) => alert.id);

describe("applyLiveFrame", () => {
  it("writes kpis frames into the summary cache", async () => {
    const queryClient = createQueryClient({ retry: false });
    const frame = makeKpiFrame([makePort({ rx_bps: 20 })]);

    await applyLiveFrame(queryClient, frame, false);

    expect(queryClient.getQueryData<KpiSnapshot>(queryKeys.kpiSummary)?.summary.rx_bps).toBe(20);
  });

  it("replaces the open list with the first alerts frame after connecting", async () => {
    const queryClient = createQueryClient({ retry: false });
    queryClient.setQueryData(openKey, { generated_at: "2026-10-26T09:00:00Z", alerts: [makeAlert({ id: 7 })] });

    await applyLiveFrame(queryClient, makeAlertsFrame([makeAlert({ id: 1 })]), false);

    expect(openIds(queryClient)).toEqual([1]);
  });

  it("upserts later alerts frames and drops resolved alerts", async () => {
    const queryClient = createQueryClient({ retry: false });
    await applyLiveFrame(
      queryClient,
      makeAlertsFrame([makeAlert({ id: 1 }), makeAlert({ id: 2, opened_at: "2026-10-26T10:01:00Z" })]),
      false,
    );

    await applyLiveFrame(queryClient, makeAlertsFrame([makeAlert({ id: 1, severity: "critical" })]), true);
    expect(queryClient.getQueryData<AlertList>(openKey)?.alerts.map((alert) => [alert.id, alert.severity])).toEqual([
      [2, "warning"],
      [1, "critical"],
    ]);

    await applyLiveFrame(
      queryClient,
      makeAlertsFrame([makeAlert({ id: 2, status: "resolved", resolved_at: "2026-10-26T10:05:00Z" })]),
      true,
    );
    expect(openIds(queryClient)).toEqual([1]);
  });

  it("drops an in-flight REST list so it cannot overwrite the live frame", async () => {
    const queryClient = createQueryClient({ retry: false });
    let respond: (list: AlertList) => void = () => undefined;
    const fetching = queryClient.fetchQuery({
      queryKey: openKey,
      queryFn: () =>
        new Promise<AlertList>((resolve) => {
          respond = resolve;
        }),
    });

    await applyLiveFrame(queryClient, makeAlertsFrame([makeAlert({ id: 1 })]), false);
    respond({ generated_at: "2026-10-26T09:00:00Z", alerts: [makeAlert({ id: 9 })] });
    await fetching.catch(() => undefined);

    expect(openIds(queryClient)).toEqual([1]);
  });

  it("leaves the cache alone for control frames", async () => {
    const queryClient = createQueryClient({ retry: false });

    await applyLiveFrame(queryClient, { type: "heartbeat", at: "2026-10-26T10:00:00Z" }, true);
    await applyLiveFrame(queryClient, { type: "hello", version: "1.0.0" }, true);

    expect(queryClient.getQueryCache().getAll()).toHaveLength(0);
  });
});
