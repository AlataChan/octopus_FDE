import { useSyncExternalStore } from "react";

const XL_QUERY = "(min-width: 1280px)";

function subscribe(callback: () => void) {
  if (typeof window === "undefined" || typeof window.matchMedia !== "function") {
    return () => {};
  }

  const mediaQuery = window.matchMedia(XL_QUERY);
  mediaQuery.addEventListener("change", callback);
  return () => mediaQuery.removeEventListener("change", callback);
}

function getSnapshot() {
  if (typeof window === "undefined" || typeof window.matchMedia !== "function") {
    return false;
  }

  return window.matchMedia(XL_QUERY).matches;
}

function getServerSnapshot() {
  return false;
}

export function useIsXl() {
  return useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);
}
