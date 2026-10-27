import { useCallback, useSyncExternalStore } from "react";

export const COMPACT_VIEWPORT_QUERY = "(max-width: 767px)";

const hasMatchMedia = (): boolean => typeof window !== "undefined" && typeof window.matchMedia === "function";

const getServerSnapshot = (): boolean => false;

export const useMediaQuery = (query: string): boolean => {
  const subscribe = useCallback(
    (onChange: () => void) => {
      if (!hasMatchMedia()) {
        return () => undefined;
      }
      const media = window.matchMedia(query);
      media.addEventListener("change", onChange);
      return () => media.removeEventListener("change", onChange);
    },
    [query],
  );
  const getSnapshot = useCallback(() => hasMatchMedia() && window.matchMedia(query).matches, [query]);
  return useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);
};
