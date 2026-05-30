import { useEffect, useMemo } from "react";

/**
 * Returns an AbortSignal that aborts when the component unmounts.
 * Use to cancel in-flight API calls on fast tab switches.
 */
export function useAbortOnUnmount(): AbortSignal {
  const controller = useMemo(() => new AbortController(), []);

  useEffect(() => {
    return () => controller.abort();
  }, [controller]);

  return controller.signal;
}
