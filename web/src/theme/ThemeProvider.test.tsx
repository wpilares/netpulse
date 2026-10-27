import { act, render, renderHook, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ThemeProvider, useTheme } from "./ThemeProvider";
import { THEME_STORAGE_KEY } from "./theme";

type SchemeListener = (event: MediaQueryListEvent) => void;

interface FakeMediaQuery {
  readonly query: MediaQueryList;
  readonly listeners: Set<SchemeListener>;
  setMatches(matches: boolean): void;
}

const createFakeMediaQuery = (matches: boolean): FakeMediaQuery => {
  const listeners = new Set<SchemeListener>();
  const state = { matches };
  const query = {
    get matches() {
      return state.matches;
    },
    media: "(prefers-color-scheme: dark)",
    onchange: null,
    addEventListener: (_type: "change", listener: SchemeListener) => {
      listeners.add(listener);
    },
    removeEventListener: (_type: "change", listener: SchemeListener) => {
      listeners.delete(listener);
    },
    addListener: vi.fn(),
    removeListener: vi.fn(),
    dispatchEvent: () => true,
  } as MediaQueryList;
  return {
    query,
    listeners,
    setMatches: (next) => {
      state.matches = next;
      for (const listener of listeners) {
        listener({ matches: next, media: query.media } as MediaQueryListEvent);
      }
    },
  };
};

const installMatchMedia = (prefersDark: boolean): FakeMediaQuery => {
  const fake = createFakeMediaQuery(prefersDark);
  vi.stubGlobal("matchMedia", () => fake.query);
  return fake;
};

const ThemeProbe = () => {
  const { preference, resolvedTheme, setPreference } = useTheme();
  return (
    <div>
      <output data-testid="preference">{preference}</output>
      <output data-testid="resolved">{resolvedTheme}</output>
      <button type="button" onClick={() => setPreference("light")}>
        light
      </button>
      <button type="button" onClick={() => setPreference("dark")}>
        dark
      </button>
      <button type="button" onClick={() => setPreference("system")}>
        system
      </button>
    </div>
  );
};

describe("ThemeProvider", () => {
  beforeEach(() => {
    localStorage.clear();
    document.documentElement.removeAttribute("data-theme");
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    localStorage.clear();
    document.documentElement.removeAttribute("data-theme");
  });

  it("applies the stored preference to the document on mount", () => {
    installMatchMedia(false);
    localStorage.setItem(THEME_STORAGE_KEY, "dark");

    render(
      <ThemeProvider>
        <ThemeProbe />
      </ThemeProvider>,
    );

    expect(screen.getByTestId("preference")).toHaveTextContent("dark");
    expect(screen.getByTestId("resolved")).toHaveTextContent("dark");
    expect(document.documentElement).toHaveAttribute("data-theme", "dark");
  });

  it("persists a new preference and updates the document attribute", () => {
    installMatchMedia(false);

    render(
      <ThemeProvider>
        <ThemeProbe />
      </ThemeProvider>,
    );

    act(() => {
      screen.getByRole("button", { name: "light" }).click();
    });

    expect(localStorage.getItem(THEME_STORAGE_KEY)).toBe("light");
    expect(document.documentElement).toHaveAttribute("data-theme", "light");
    expect(screen.getByTestId("resolved")).toHaveTextContent("light");
  });

  it("clears the attribute and the stored value when returning to system", () => {
    installMatchMedia(true);
    localStorage.setItem(THEME_STORAGE_KEY, "light");

    render(
      <ThemeProvider>
        <ThemeProbe />
      </ThemeProvider>,
    );

    act(() => {
      screen.getByRole("button", { name: "system" }).click();
    });

    expect(localStorage.getItem(THEME_STORAGE_KEY)).toBeNull();
    expect(document.documentElement).not.toHaveAttribute("data-theme");
    expect(screen.getByTestId("preference")).toHaveTextContent("system");
    expect(screen.getByTestId("resolved")).toHaveTextContent("dark");
  });

  it("follows system scheme changes while the preference is system", () => {
    const media = installMatchMedia(false);

    render(
      <ThemeProvider>
        <ThemeProbe />
      </ThemeProvider>,
    );

    expect(screen.getByTestId("resolved")).toHaveTextContent("light");

    act(() => {
      media.setMatches(true);
    });

    expect(screen.getByTestId("resolved")).toHaveTextContent("dark");
    expect(document.documentElement).not.toHaveAttribute("data-theme");
  });

  it("ignores system scheme changes under an explicit preference", () => {
    const media = installMatchMedia(false);
    localStorage.setItem(THEME_STORAGE_KEY, "light");

    render(
      <ThemeProvider>
        <ThemeProbe />
      </ThemeProvider>,
    );

    act(() => {
      media.setMatches(true);
    });

    expect(screen.getByTestId("resolved")).toHaveTextContent("light");
  });

  it("stops listening to the media query on unmount", () => {
    const media = installMatchMedia(false);

    const { unmount } = render(
      <ThemeProvider>
        <ThemeProbe />
      </ThemeProvider>,
    );
    expect(media.listeners.size).toBe(1);

    unmount();

    expect(media.listeners.size).toBe(0);
  });

  it("resolves to light when matchMedia is unavailable", () => {
    vi.stubGlobal("matchMedia", undefined);

    render(
      <ThemeProvider>
        <ThemeProbe />
      </ThemeProvider>,
    );

    expect(screen.getByTestId("resolved")).toHaveTextContent("light");
  });
});

describe("useTheme", () => {
  it("throws outside a ThemeProvider", () => {
    expect(() => renderHook(() => useTheme())).toThrow("useTheme must be used within a ThemeProvider");
  });
});
