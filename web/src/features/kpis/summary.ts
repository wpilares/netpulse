import { useEffect, useState } from "react";
import { type KpiSnapshot, parseKpiSnapshot } from "../telemetry/frames";

const SUMMARY_PATH = "/api/v1/kpis/summary";

export const fetchKpiSummary = async (fetcher: typeof fetch, signal?: AbortSignal): Promise<KpiSnapshot | null> => {
  try {
    const response = await fetcher(SUMMARY_PATH, {
      headers: { Accept: "application/json" },
      ...(signal === undefined ? {} : { signal }),
    });
    return response.ok ? parseKpiSnapshot(await response.json()) : null;
  } catch {
    return null;
  }
};

export const useKpiSummary = (fetcher: typeof fetch): KpiSnapshot | null => {
  const [snapshot, setSnapshot] = useState<KpiSnapshot | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    void fetchKpiSummary(fetcher, controller.signal).then((next) => {
      if (!controller.signal.aborted) {
        setSnapshot(next);
      }
    });
    return () => controller.abort();
  }, [fetcher]);

  return snapshot;
};
