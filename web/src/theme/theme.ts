export type ThemePreference = "light" | "dark" | "system";
export type ResolvedTheme = "light" | "dark";
export type ThemeStorage = Pick<Storage, "getItem" | "setItem" | "removeItem">;

export const THEME_STORAGE_KEY = "netpulse.theme";
export const DARK_SCHEME_QUERY = "(prefers-color-scheme: dark)";
export const THEME_PREFERENCES: readonly ThemePreference[] = ["light", "dark", "system"];

export const isThemePreference = (value: unknown): value is ThemePreference =>
  typeof value === "string" && THEME_PREFERENCES.some((preference) => preference === value);

export const readStoredTheme = (storage: ThemeStorage | null): ThemePreference => {
  if (storage === null) {
    return "system";
  }
  try {
    const stored = storage.getItem(THEME_STORAGE_KEY);
    return isThemePreference(stored) ? stored : "system";
  } catch {
    return "system";
  }
};

export const writeStoredTheme = (storage: ThemeStorage | null, preference: ThemePreference): void => {
  if (storage === null) {
    return;
  }
  try {
    if (preference === "system") {
      storage.removeItem(THEME_STORAGE_KEY);
    } else {
      storage.setItem(THEME_STORAGE_KEY, preference);
    }
  } catch {
    return;
  }
};

export const resolveTheme = (preference: ThemePreference, prefersDark: boolean): ResolvedTheme => {
  if (preference === "system") {
    return prefersDark ? "dark" : "light";
  }
  return preference;
};

export const applyThemeAttribute = (root: HTMLElement, preference: ThemePreference): void => {
  if (preference === "system") {
    root.removeAttribute("data-theme");
  } else {
    root.setAttribute("data-theme", preference);
  }
};
