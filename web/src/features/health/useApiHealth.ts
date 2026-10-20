import { useEffect, useState } from "react";
import { type ApiHealth, fetchApiHealth } from "./health";

export const useApiHealth = (fetcher: typeof fetch, pollIntervalMs: number): ApiHealth => {
  const [health, setHealth] = useState<ApiHealth>({ kind: "loading" });

  useEffect(() => {
    const controller = new AbortController();
    const refresh = async () => {
      const next = await fetchApiHealth(fetcher, controller.signal);
      if (!controller.signal.aborted) {
        setHealth(next);
      }
    };
    void refresh();
    const timer = window.setInterval(() => void refresh(), pollIntervalMs);
    return () => {
      controller.abort();
      window.clearInterval(timer);
    };
  }, [fetcher, pollIntervalMs]);

  return health;
};
