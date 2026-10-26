import { isOneOf, isRecord } from "../../lib/guards";

const HEALTH_PATH = "/health";

const SERVICE_STATUSES = ["ok", "degraded"] as const;
const DATABASE_STATES = ["up", "down", "disabled"] as const;

export type ServiceStatus = (typeof SERVICE_STATUSES)[number];
export type DatabaseState = (typeof DATABASE_STATES)[number];

export interface ApiHealthReport {
  readonly status: ServiceStatus;
  readonly database: DatabaseState;
  readonly version: string;
}

export type ApiHealth =
  | { readonly kind: "loading" }
  | { readonly kind: "offline" }
  | { readonly kind: "online"; readonly report: ApiHealthReport };

export const parseApiHealth = (payload: unknown): ApiHealthReport | null => {
  if (!isRecord(payload)) {
    return null;
  }
  const { status, database, version } = payload;
  if (!isOneOf(SERVICE_STATUSES, status) || !isOneOf(DATABASE_STATES, database) || typeof version !== "string") {
    return null;
  }
  return { status, database, version };
};

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
