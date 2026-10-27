import { act, renderHook } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { useMediaQuery } from "./useMediaQuery";

type Listener = () => void;

const stubMatchMedia = (matches: boolean) => {
  const listeners = new Set<Listener>();
  const media = {
    matches,
    media: "(max-width: 767px)",
    addEventListener: (_type: string, listener: Listener) => listeners.add(listener),
    removeEventListener: (_type: string, listener: Listener) => listeners.delete(listener),
  };
  vi.stubGlobal("matchMedia", () => media);
  return {
    change: (next: boolean) => {
      media.matches = next;
      for (const listener of listeners) {
        listener();
      }
    },
    listeners,
  };
};

describe("useMediaQuery", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("is false when matchMedia is unavailable", () => {
    const { result } = renderHook(() => useMediaQuery("(max-width: 767px)"));

    expect(result.current).toBe(false);
  });

  it("reflects the media query and follows changes", () => {
    const media = stubMatchMedia(true);
    const { result, unmount } = renderHook(() => useMediaQuery("(max-width: 767px)"));

    expect(result.current).toBe(true);

    act(() => media.change(false));
    expect(result.current).toBe(false);

    unmount();
    expect(media.listeners.size).toBe(0);
  });
});
