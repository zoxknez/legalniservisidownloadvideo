import { Database, Loader2, Trash2 } from "lucide-react";
import type { DrmHealth } from "../../types/app";

interface DrmKeyCacheProps {
  health: DrmHealth | null;
  clearing: boolean;
  onClearCache: () => void;
}

export function DrmKeyCache({ health, clearing, onClearCache }: DrmKeyCacheProps) {
  return (
    <div className="glass-panel p-5 rounded-xl border border-glass">
      <h3 className="text-sm font-bold text-white mb-4 flex items-center gap-2">
        <Database className="w-4 h-4 text-indigo-400" /> Key Cache
      </h3>
      {health ? (
        <div className="flex flex-col gap-3">
          <div className="grid gap-2" style={{gridTemplateColumns:"1fr 1fr"}}>
            <div className="rounded-lg bg-white/[0.04] border border-white/[0.06] p-3 text-center">
              <div className="text-2xl font-extrabold text-indigo-400">{health.key_cache.alive_entries}</div>
              <div className="text-[10px] text-text-muted mt-0.5">Aktivni ključevi</div>
            </div>
            <div className="rounded-lg bg-white/[0.04] border border-white/[0.06] p-3 text-center">
              <div className="text-2xl font-extrabold text-slate-400">{health.key_cache.total_entries}</div>
              <div className="text-[10px] text-text-muted mt-0.5">Ukupno unosa</div>
            </div>
          </div>
          <p className="text-[10px] text-text-muted">
            Cache TTL: 12h. Keširanim sadržajima ne šalje se novi license request – brži download.
          </p>
          <button onClick={onClearCache} disabled={clearing || health.key_cache.total_entries === 0}
            className="flex items-center justify-center gap-2 py-2 rounded-lg text-xs font-bold text-red-300 border border-red-500/20 bg-red-500/5 hover:bg-red-500/15 transition-all disabled:opacity-40">
            {clearing ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Trash2 className="w-3.5 h-3.5" />}
            Očisti Cache
          </button>

          {health.provider_certs_fetched.length > 0 && (
            <div>
              <p className="text-[10px] text-text-muted mb-1 font-semibold">Provider sertifikati:</p>
              <div className="flex flex-wrap gap-1">
                {health.provider_certs_fetched.map(svc => (
                  <span key={svc} className="text-[10px] font-bold text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 px-2 py-0.5 rounded-full">
                    ✓ {svc}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      ) : (
        <p className="text-xs text-text-muted">Učitavanje...</p>
      )}
    </div>
  );
}
