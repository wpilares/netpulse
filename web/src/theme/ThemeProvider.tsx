import {
  createContext,
  type ReactNode,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  useSyncExternalStore,
} from "react";
import {
  applyThemeAttribute,
  DARK_SCHEME_QUERY,
  type ResolvedTheme,
  readStoredTheme,
  resolveTheme,
  type ThemePreference,
  type ThemeStorage,
  writeStoredTheme,
} from "./theme";

export interface ThemeContextValue {
  readonly preference: ThemePreference;
  readonly resolvedTheme: ResolvedTheme;
  readonly setPreference: (preference: ThemePreference) => void;
}

const ThemeContext = createContext<ThemeContextValue | null>(null);

const getDefaultStorage = (): ThemeStorage | null => {
  try {
    return window.localStorage;
  } catch {
    return null;
  }
};

const hasMatchMedia = (): boolean => typeof window !== "undefined" && typeof window.matchMedia === "function";

const subscribeToSystemScheme = (onChange: () => void): (() => void) => {
  if (!hasMatchMedia()) {
    return () => undefined;
  }
  const media = window.matchMedia(DARK_SCHEME_QUERY);
  media.addEventListener("change", onChange);
  return () => media.removeEventListener("change", onChange);
};

const getSystemPrefersDark = (): boolean => hasMatchMedia() && window.matchMedia(DARK_SCHEME_QUERY).matches;

const getServerPrefersDark = (): boolean => false;

export interface ThemeProviderProps {
  readonly children: ReactNode;
}

export const ThemeProvider = ({ children }: ThemeProviderProps) => {
  const [storage] = useState(getDefaultStorage);
  const [preference, setPreferenceState] = useState<ThemePreference>(() => readStoredTheme(storage));
  const prefersDark = useSyncExternalStore(subscribeToSystemScheme, getSystemPrefersDark, getServerPrefersDark);

  useEffect(() => {
    applyThemeAttribute(document.documentElement, preference);
  }, [preference]);

  const setPreference = useCallback(
    (next: ThemePreference) => {
      setPreferenceState(next);
      writeStoredTheme(storage, next);
    },
    [storage],
  );

  const value = useMemo<ThemeContextValue>(
    () => ({ preference, resolvedTheme: resolveTheme(preference, prefersDark), setPreference }),
    [preference, prefersDark, setPreference],
  );

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
};

export const useTheme = (): ThemeContextValue => {
  const context = useContext(ThemeContext);
  if (context === null) {
    throw new Error("useTheme must be used within a ThemeProvider");
  }
  return context;
};
