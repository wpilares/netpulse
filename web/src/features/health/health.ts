import { type ApiHealthReport, healthReportSchema, parseWith } from "../../api/schemas";

export type { ApiHealthReport, DatabaseState, ServiceStatus } from "../../api/schemas";

export type ApiHealth =
  | { readonly kind: "loading" }
  | { readonly kind: "offline" }
  | { readonly kind: "online"; readonly report: ApiHealthReport };

export interface HealthQueryResult {
  readonly status: "pending" | "error" | "success";
  readonly data: ApiHealthReport | undefined;
}

export const parseApiHealth = parseWith(healthReportSchema);

export const toApiHealth = ({ status, data }: HealthQueryResult): ApiHealth => {
  if (status === "error") {
    return { kind: "offline" };
  }
  if (data === undefined) {
    return { kind: "loading" };
  }
  return { kind: "online", report: data };
};
