export type ClassValue = string | false | null | undefined;

export const cx = (...values: readonly ClassValue[]): string =>
  values.filter((value): value is string => typeof value === "string" && value.length > 0).join(" ");
