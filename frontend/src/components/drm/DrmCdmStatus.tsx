import {
  ShieldCheck, Loader2, CheckCircle2, AlertCircle, RotateCcw,
} from "lucide-react";
import type { DrmHealth } from "../../types/app";

interface DrmCdmStatusProps {
  health: DrmHealth | null;
  loading: boolean;
  reloading: boolean;
  onReload: () => void;
}

export function DrmCdmStatus({ health, loading, reloading, onReload }: DrmCdmStatusProps) {
  const sl = health?.wvd_metadata?.security_level ?? 0;
  const slColor = sl === 1 ? "#10b981" : sl === 2 ? "#f59e0b" : sl === 3 ? "#6366f1" : "#64748b";
  const slBg = sl === 1 ? "rgba(16,185,129,0.12)" : sl === 2 ? "rgba(245,158,11,0.12)" : sl === 3 ? "rgba(99,102,241,0.12)" : "rgba(100,116,139,0.12)";

  return (
    <div className="glass-panel p-5 rounded-xl border border-glass relative overflow-hidden">
      <div className="console-scanline" />
      <h3 className="text-sm font-bold text-white mb-4 flex items-center gap-2">
        <ShieldCheck className="w-4 h-4 text-violet-400" /> CDM Status
      </h3>
      {loading && !health ? (
        <div className="flex items-center gap-2 text-text-muted text-xs"><Loader2 className="w-4 h-4 animate-spin" /> Učitavanje...</div>
      ) : health ? (
        <div className="flex flex-col gap-3">
          <div className="flex items-center gap-2">
            {health.cdm_ready ? (
              <span className="flex items-center gap-1.5 text-xs font-bold text-emerald-400 bg-emerald-500/10 border border-emerald-500/25 px-2.5 py-1 rounded-full">
                <CheckCircle2 className="w-3.5 h-3.5" /> CDM Spreman
              </span>
            ) : (
              <span className="flex items-center gap-1.5 text-xs font-bold text-red-400 bg-red-500/10 border border-red-500/25 px-2.5 py-1 rounded-full">
                <AlertCircle className="w-3.5 h-3.5" /> CDM Nije Spreman
              </span>
            )}
            {health.legacy_mode && (
              <span className="text-xs text-amber-400 bg-amber-500/10 border border-amber-500/20 px-2 py-0.5 rounded-full font-semibold">Legacy Mode</span>
            )}
          </div>

          {health.wvd_metadata.is_valid && (
            <div className="rounded-xl p-3 border" style={{background: slBg, borderColor: slColor + "40"}}>
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs text-text-muted font-semibold">Security Level</span>
                <span className="text-xs font-extrabold" style={{color: slColor}}>
                  L{health.wvd_metadata.security_level ?? "?"}
                </span>
              </div>
              <p className="text-xs font-bold" style={{color: slColor}}>
                {health.wvd_metadata.security_level_name}
              </p>
              {sl === 3 && (
                <p className="text-[10px] text-text-muted mt-1">
                  Software CDM – dovoljno za 1080p/SDR. L1 zahtijeva hardverski TEE čip.
                </p>
              )}
              {sl === 1 && (
                <p className="text-[10px] text-text-muted mt-1">
                  Hardverski zaštićen – maksimalna razina zaštite sadržaja.
                </p>
              )}
            </div>
          )}

          <div className="flex flex-col gap-1.5 text-xs">
            {[
              ["Tip uređaja", health.wvd_metadata.device_type ?? "—"],
              ["WVD verzija", health.wvd_metadata.wvd_version != null ? `v${health.wvd_metadata.wvd_version}` : "—"],
              ["Veličina fajla", health.wvd_metadata.file_size ? `${health.wvd_metadata.file_size.toLocaleString()} B` : "—"],
              ["Private key", health.wvd_metadata.private_key_size > 0 ? `${health.wvd_metadata.private_key_size * 8}-bit RSA` : "—"],
              ["Client ID", health.wvd_metadata.client_id_size > 0 ? `${health.wvd_metadata.client_id_size} B` : "—"],
              ["pywidevine", health.pywidevine_version ?? "—"],
            ].map(([label, val]) => (
              <div key={label} className="flex justify-between items-center py-0.5 border-b border-white/[0.04]">
                <span className="text-text-muted">{label}:</span>
                <span className="font-mono text-white text-[11px]">{val}</span>
              </div>
            ))}
            <div className="flex justify-between items-center py-0.5">
              <span className="text-text-muted">WVD putanja:</span>
              <span className="font-mono text-violet-300 text-[10px] max-w-[180px] truncate" title={health.wvd_file ?? "—"}>
                {health.wvd_file ? health.wvd_file.split(/[\\/]/).pop() : "—"}
              </span>
            </div>
          </div>

          {health.wvd_metadata.error && (
            <div className="flex items-start gap-2 bg-red-500/10 border border-red-500/20 rounded-lg p-2.5 text-xs text-red-300">
              <AlertCircle className="w-3.5 h-3.5 flex-shrink-0 mt-0.5" />
              <span>{health.wvd_metadata.error}</span>
            </div>
          )}

          <button onClick={onReload} disabled={reloading}
            className="w-full flex items-center justify-center gap-2 py-2 rounded-lg text-xs font-bold text-violet-300 border border-violet-500/30 bg-violet-500/10 hover:bg-violet-500/20 transition-all disabled:opacity-50">
            {reloading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <RotateCcw className="w-3.5 h-3.5" />}
            Reload CDM (novi device.wvd)
          </button>
        </div>
      ) : (
        <p className="text-xs text-text-muted">Podaci nisu dostupni.</p>
      )}
    </div>
  );
}
