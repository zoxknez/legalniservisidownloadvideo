import type { CSSProperties } from "react";

/** Inline styles with CSS custom properties (e.g. `--btn-grad-start`). */
export function cssVars(props: Record<string, string | number>): CSSProperties {
  return props as CSSProperties;
}
