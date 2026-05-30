import { useState, useEffect, useCallback } from "react";
import { Shield, RefreshCw, Loader2 } from "lucide-react";
import { apiFetch } from "../lib/api";
import type { DrmHealth } from "../types/app";
import { useAbortOnUnmount } from "../hooks/useAbortOnUnmount";
import { DrmCdmStatus } from "./drm/DrmCdmStatus";
import { DrmKeyCache } from "./drm/DrmKeyCache";
import { DrmRecommendations, DrmSecurityLevels } from "./drm/DrmInfoPanel";
import { DrmTestKeys } from "./drm/DrmTestKeys";
import { DrmCertPrefetch } from "./drm/DrmCertPrefetch";

export function DrmPanel() {
  const [health, setHealth] = useState<DrmHealth | null>(null);
  const [loading, setLoading] = useState(false);
  const [reloading, setReloading] = useState(false);
  const [clearing, setClearing] = useState(false);
  const abortSignal = useAbortOnUnmount();

  const fetchHealth = useCallback(async () => {
    setLoading(true);
    try {
      const r = await apiFetch("/api/drm/health", { signal: abortSignal });
      const d = await r.json();
      setHealth(d);
    } catch { /* ignore — aborted or network error */ }
    setLoading(false);
  }, [abortSignal]);

  useEffect(() => { fetchHealth(); }, [fetchHealth]);

  const handleReload = async () => {
    setReloading(true);
    try {
      const r = await apiFetch("/api/drm/reload", { method: "POST" });
      const d = await r.json();
      if (d.health) setHealth(d.health);
    } catch { /* ignore */ }
    setReloading(false);
  };

  const handleClearCache = async () => {
    setClearing(true);
    try {
      await apiFetch("/api/drm/cache/clear", { method: "POST" });
      await fetchHealth();
    } catch { /* ignore */ }
    setClearing(false);
  };

  return (
    <div key="drm" className="tab-content tab-content-drm">
      {/* Header */}
      <div className="tab-page-header mb-6" style={{background:"linear-gradient(135deg,rgba(139,92,246,0.15),rgba(99,102,241,0.08))",border:"1px solid rgba(139,92,246,0.2)",borderRadius:16,padding:"20px 24px",display:"flex",alignItems:"center",gap:16}}>
        <div style={{width:52,height:52,borderRadius:14,background:"linear-gradient(135deg,#7c3aed,#4f46e5)",display:"flex",alignItems:"center",justifyContent:"center",boxShadow:"0 0 24px rgba(124,58,237,0.5)"}}>
          <Shield style={{width:26,height:26,color:"white"}} />
        </div>
        <div style={{flex:1}}>
          <h2 className="text-xl font-extrabold text-white mb-0.5 flex items-center gap-2">
            <Shield className="w-5 h-5 text-violet-400" /> DRM / Widevine Kontrolna Tabla
          </h2>
          <p className="text-xs text-text-muted">CDM dijagnostika, key cache, test licence i provider sertifikati</p>
        </div>
        <button onClick={fetchHealth} disabled={loading}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold text-violet-300 border border-violet-500/30 bg-violet-500/10 hover:bg-violet-500/20 transition-all disabled:opacity-50">
          {loading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <RefreshCw className="w-3.5 h-3.5" />} Osvježi
        </button>
      </div>

      <div className="grid gap-5" style={{gridTemplateColumns:"1fr 1fr"}}>
        {/* LEFT COL */}
        <div className="flex flex-col gap-5">
          <DrmCdmStatus health={health} loading={loading} reloading={reloading} onReload={handleReload} />
          <DrmKeyCache health={health} clearing={clearing} onClearCache={handleClearCache} />
          <DrmRecommendations recommendations={health?.recommendations ?? []} />
        </div>

        {/* RIGHT COL */}
        <div className="flex flex-col gap-5">
          <DrmTestKeys />
          <DrmCertPrefetch onHealthRefresh={fetchHealth} />
          <DrmSecurityLevels />
        </div>
      </div>
    </div>
  );
}
