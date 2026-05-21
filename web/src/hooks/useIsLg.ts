import { useSyncExternalStore } from "react";

const LG_QUERY = "(min-width: 1024px)";

function subscribe(callback: () => void) {
  if (typeof window === "undefined" || typeof window.matchMedia !== "function") {
    return () => {};
  }

  const mediaQuery = window.matchMedia(LG_QUERY);
  mediaQuery.addEventListener("change", callback);
  return () => mediaQuery.removeEventListener("change", callback);
}

function getSnapshot() {
  if (typeof window === "undefined" || typeof window.matchMedia !== "function") {
    return false;
  }

  return window.matchMedia(LG_QUERY).matches;
}

function getServerSnapshot() {
  return false;
}

export function useIsLg() {
  return useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);
}
