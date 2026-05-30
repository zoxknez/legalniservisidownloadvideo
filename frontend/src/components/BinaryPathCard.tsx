import { cssVars } from "../utils/cssVars";
import { useState } from "react";

export interface BinaryPathCardProps {
  name: string;
  found: boolean;
  pathValue: string;
  onChange: (val: string) => void;
  showToast: (msg: string, type: "success" | "error" | "info") => void;
}

export function BinaryPathCard({ name, found, pathValue, onChange, showToast }: BinaryPathCardProps) {
  const [copied, setCopied] = useState<boolean>(false);
  const display = name.toUpperCase().replace("_", ".");
  return (
    <div
      className="exec-monitor-card flex flex-col gap-3 group"
      style={cssVars({
        "--hover-border": found ? "rgba(16, 185, 129, 0.2)" : "rgba(239, 68, 68, 0.2)"
      })}
    >
      <div className="flex justify-between items-center">
        <div className="flex items-center gap-2">
          <span className={`exec-status-dot ${found ? "active" : "missing"}`} />
          <span className="text-sm font-extrabold text-white tracking-wide">{display}</span>
        </div>
        <button
          type="button"
          title="Kopiraj putanju"
          onClick={async () => {
            try {
              await navigator.clipboard.writeText(pathValue || "");
              setCopied(true);
              setTimeout(() => setCopied(false), 2000);
              showToast(`${display} putanja kopirana!`, "success");
            } catch {
              /* clipboard unavailable */
            }
          }}
          className="exec-copy-btn text-text-muted hover:text-white p-1 rounded transition-colors"
        >
          {copied ? (
            <svg className="w-3.5 h-3.5 text-emerald-400" fill="none" stroke="currentColor" strokeWidth="2.5" viewBox="0 0 24 24">
              <polyline points="20 6 9 17 4 12" />
            </svg>
          ) : (
            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" strokeWidth="2.5" viewBox="0 0 24 24">
              <rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
              <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
            </svg>
          )}
        </button>
      </div>
      
      <input
        type="text"
        value={pathValue || ""}
        onChange={(e) => onChange(e.target.value)}
        title={pathValue || ""}
        className="py-2 px-3 text-[11px] font-mono settings-path-input input-premium"
        style={cssVars({
          "--focused-border": found ? "#10b981" : "#ef4444",
          "--focused-glow": found ? "rgba(16, 185, 129, 0.25)" : "rgba(239, 68, 68, 0.25)"
        })}
      />
    </div>
  );
}
