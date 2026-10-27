import { describe, expect, it, vi } from "vitest";
import {
  applyThemeAttribute,
  isThemePreference,
  readStoredTheme,
  resolveTheme,
  THEME_STORAGE_KEY,
  type ThemeStorage,
  writeStoredTheme,
} from "./theme";

const createStorage = (initial: Record<string, string> = {}): ThemeStorage & { readonly data: Map<string, string> } => {
  const data = new Map(Object.entries(initial));
  return {
    data,
    getItem: (key) => data.get(key) ?? null,
    setItem: (key, value) => {
      data.set(key, value);
    },
    removeItem: (key) => {
      data.delete(key);
    },
  };
};

describe("isThemePreference", () => {
  it("accepts the three preferences and nothing else", () => {
    expect(isThemePreference("light")).toBe(true);
    expect(isThemePreference("dark")).toBe(true);
    expect(isThemePreference("system")).toBe(true);
    expect(isThemePreference("auto")).toBe(false);
    expect(isThemePreference(null)).toBe(false);
    expect(isThemePreference(42)).toBe(false);
  });
});

describe("readStoredTheme", () => {
  it("returns the stored preference under the netpulse key", () => {
    expect(readStoredTheme(createStorage({ [THEME_STORAGE_KEY]: "dark" }))).toBe("dark");
  });

  it("falls back to system when nothing is stored or the value is unknown", () => {
    expect(readStoredTheme(createStorage())).toBe("system");
    expect(readStoredTheme(createStorage({ [THEME_STORAGE_KEY]: "sepia" }))).toBe("system");
    expect(readStoredTheme(null)).toBe("system");
  });

  it("falls back to system when storage throws", () => {
    const storage: ThemeStorage = {
      getItem: () => {
        throw new Error("denied");
      },
      setItem: vi.fn(),
      removeItem: vi.fn(),
    };

    expect(readStoredTheme(storage)).toBe("system");
  });
});

describe("writeStoredTheme", () => {
  it("persists explicit preferences and clears the key for system", () => {
    const storage = createStorage();

    writeStoredTheme(storage, "light");
    expect(storage.data.get(THEME_STORAGE_KEY)).toBe("light");

    writeStoredTheme(storage, "system");
    expect(storage.data.has(THEME_STORAGE_KEY)).toBe(false);
  });

  it("swallows storage failures", () => {
    const storage: ThemeStorage = {
      getItem: () => null,
      setItem: () => {
        throw new Error("quota");
      },
      removeItem: () => {
        throw new Error("quota");
      },
    };

    expect(() => writeStoredTheme(storage, "dark")).not.toThrow();
    expect(() => writeStoredTheme(storage, "system")).not.toThrow();
    expect(() => writeStoredTheme(null, "dark")).not.toThrow();
  });
});

describe("resolveTheme", () => {
  it("returns explicit preferences unchanged", () => {
    expect(resolveTheme("light", true)).toBe("light");
    expect(resolveTheme("dark", false)).toBe("dark");
  });

  it("follows the system scheme for the system preference", () => {
    expect(resolveTheme("system", true)).toBe("dark");
    expect(resolveTheme("system", false)).toBe("light");
  });
});

describe("applyThemeAttribute", () => {
  it("sets data-theme for explicit preferences and removes it for system", () => {
    const root = document.createElement("html");

    applyThemeAttribute(root, "dark");
    expect(root.getAttribute("data-theme")).toBe("dark");

    applyThemeAttribute(root, "light");
    expect(root.getAttribute("data-theme")).toBe("light");

    applyThemeAttribute(root, "system");
    expect(root.hasAttribute("data-theme")).toBe(false);
  });
});
