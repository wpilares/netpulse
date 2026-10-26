export const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null;

export const isOneOf = <T extends string>(options: readonly T[], value: unknown): value is T =>
  options.some((option) => option === value);

export const isNullableNumber = (value: unknown): value is number | null => value === null || typeof value === "number";

export const isArrayOf = <T>(value: unknown, guard: (item: unknown) => item is T): value is T[] =>
  Array.isArray(value) && value.every(guard);
