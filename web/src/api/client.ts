import axios, { type AxiosRequestConfig, isAxiosError, isCancel } from "axios";
import type { z } from "zod";
import {
  type Alert,
  type AlertList,
  type AlertStatusFilter,
  type ApiHealthReport,
  alertListSchema,
  alertSchema,
  healthReportSchema,
  type KpiSnapshot,
  kpiSnapshotSchema,
  type Topology,
  topologySchema,
} from "./schemas";

export type ApiErrorKind = "network" | "not_found" | "unavailable" | "invalid";

export class ApiError extends Error {
  constructor(
    readonly kind: ApiErrorKind,
    message: string,
    readonly status: number | undefined = undefined,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export const isApiError = (error: unknown): error is ApiError => error instanceof ApiError;

export type FetchImpl = (input: URL | Request | string, init?: RequestInit) => Promise<Response>;

export interface ApiClientOptions {
  readonly baseURL?: string;
  readonly fetchImpl?: FetchImpl;
  readonly timeoutMs?: number;
}

export interface ListAlertsParams {
  readonly status: AlertStatusFilter;
  readonly limit: number;
}

export interface ApiClient {
  getHealth(signal?: AbortSignal): Promise<ApiHealthReport>;
  getKpiSummary(signal?: AbortSignal): Promise<KpiSnapshot>;
  getTopology(signal?: AbortSignal): Promise<Topology>;
  listAlerts(params: ListAlertsParams, signal?: AbortSignal): Promise<AlertList>;
  acknowledgeAlert(id: number): Promise<Alert>;
}

const DEFAULT_TIMEOUT_MS = 10_000;
const HEALTH_PATH = "/health";
const SUMMARY_PATH = "/api/v1/kpis/summary";
const TOPOLOGY_PATH = "/api/v1/topology";
const ALERTS_PATH = "/api/v1/alerts";
const HEALTH_STATUSES: ReadonlySet<number> = new Set([200, 503]);

const toApiError = (error: unknown): ApiError => {
  if (error instanceof ApiError) {
    return error;
  }
  if (isAxiosError(error)) {
    const status = error.response?.status;
    if (status === undefined) {
      return new ApiError("network", isCancel(error) ? "request cancelled" : "API unreachable");
    }
    if (status === 404) {
      return new ApiError("not_found", "resource not found", status);
    }
    if (status === 503) {
      return new ApiError("unavailable", "API unavailable", status);
    }
    return new ApiError("unavailable", `request failed with status ${status}`, status);
  }
  return new ApiError("network", error instanceof Error ? error.message : "request failed");
};

const decode = <T>(schema: z.ZodType<T>, payload: unknown): T => {
  const result = schema.safeParse(payload);
  if (!result.success) {
    throw new ApiError("invalid", "response has an unexpected shape");
  }
  return result.data;
};

const withSignal = (signal: AbortSignal | undefined): AxiosRequestConfig => (signal === undefined ? {} : { signal });

export const createApiClient = ({
  baseURL = "",
  fetchImpl,
  timeoutMs = DEFAULT_TIMEOUT_MS,
}: ApiClientOptions = {}): ApiClient => {
  const http = axios.create({
    baseURL,
    adapter: "fetch",
    timeout: timeoutMs,
    headers: { Accept: "application/json" },
    ...(fetchImpl === undefined ? {} : { env: { fetch: fetchImpl } }),
  });
  http.interceptors.response.use(
    (response) => response,
    (error: unknown) => Promise.reject(toApiError(error)),
  );

  return {
    getHealth: async (signal) => {
      const response = await http.get<unknown>(HEALTH_PATH, {
        ...withSignal(signal),
        validateStatus: (status) => HEALTH_STATUSES.has(status),
      });
      return decode(healthReportSchema, response.data);
    },
    getKpiSummary: async (signal) => {
      const response = await http.get<unknown>(SUMMARY_PATH, withSignal(signal));
      return decode(kpiSnapshotSchema, response.data);
    },
    getTopology: async (signal) => {
      const response = await http.get<unknown>(TOPOLOGY_PATH, withSignal(signal));
      return decode(topologySchema, response.data);
    },
    listAlerts: async ({ status, limit }, signal) => {
      const response = await http.get<unknown>(ALERTS_PATH, { ...withSignal(signal), params: { status, limit } });
      return decode(alertListSchema, response.data);
    },
    acknowledgeAlert: async (id) => {
      const response = await http.post<unknown>(`${ALERTS_PATH}/${id}/ack`);
      return decode(alertSchema, response.data);
    },
  };
};
