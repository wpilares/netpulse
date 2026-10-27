import { type ApiHealthReport, healthReportSchema, parseWith } from "../../api/schemas";

export type { ApiHealthReport, DatabaseState, ServiceStatus } from "../../api/schemas";

const HEALTH_PATH = "/health";

export type ApiHealth =
  | { readonly kind: "loading" }
  | { readonly kind: "offline" }
  | { readonly kind: "online"; readonly report: ApiHealthReport };

export const parseApiHealth = parseWith(healthReportSchema);

export const fetchApiHealth = async (fetcher: typeof fetch, signal?: AbortSignal): Promise<ApiHealth> => {
  try {
    const response = await fetcher(HEALTH_PATH, {
      headers: { Accept: "application/json" },
      ...(signal === undefined ? {} : { signal }),
    });
    const report = parseApiHealth(await response.json());
    return report === null ? { kind: "offline" } : { kind: "online", report };
  } catch {
    return { kind: "offline" };
  }
};
