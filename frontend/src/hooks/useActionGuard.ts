import { useCallback, useRef, useState } from "react";

/**
 * Prevents double-submission of async actions.
 * Returns [execute, isPending] where execute wraps the action
 * and ignores additional calls while one is in-flight.
 */
export function useActionGuard<Args extends unknown[], R>(
  action: (...args: Args) => Promise<R>,
): [(...args: Args) => Promise<R | undefined>, boolean] {
  const [pending, setPending] = useState(false);
  const pendingRef = useRef(false);

  const guarded = useCallback(
    async (...args: Args): Promise<R | undefined> => {
      if (pendingRef.current) return undefined;
      pendingRef.current = true;
      setPending(true);
      try {
        return await action(...args);
      } finally {
        pendingRef.current = false;
        setPending(false);
      }
    },
    [action],
  );

  return [guarded, pending];
}
