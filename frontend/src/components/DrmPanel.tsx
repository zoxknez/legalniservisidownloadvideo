import { useState, useEffect, useCallback } from "react";
import { Shield, RefreshCw, Loader2, Settings } from "lucide-react";
import { apiFetch, parseApiError } from "../lib/api";
import type { DrmHealth } from "../types/app";
import { useAbortOnUnmount } from "../hooks/useAbortOnUnmount";
import { useAppShellSlice } from "../context/appStore";
import { DrmCdmStatus } from "./drm/DrmCdmStatus";
import { DrmKeyCache } from "./drm/DrmKeyCache";
import { DrmRecommendations, DrmSecurityLevels } from "./drm/DrmInfoPanel";
import { DrmTestKeys } from "./drm/DrmTestKeys";
import { DrmCertPrefetch } from "./drm/DrmCertPrefetch";

export function DrmPanel() {
  const { showToast, setActiveTab } = useAppShellSlice();
  const [health, setHealth] = useState<DrmHealth | null>(null);
  const [loading, setLoading] = useState(false);
  const [reloading, setReloading] = useState(false);
  const [clearing, setClearing] = useState(false);
  const abortSignal = useAbortOnUnmount();

  const fetchHealth = useCallback(async () => {
    setLoading(true);
    try {
      const r = await apiFetch("/api/drm/health", { signal: abortSignal });
      if (!r.ok) {
        showToast(await parseApiError(r, "DRM dijagnostika nije dostupna."), "error");
        return;
      }
      setHealth(await r.json());
    } catch (e: unknown) {
      if (e instanceof Error && e.name !== "AbortError") {
        showToast(e.message || "Mrežna greška pri učitavanju DRM statusa.", "error");
      }
    } finally {
      setLoading(false);
    }
  }, [abortSignal, showToast]);

  useEffect(() => { fetchHealth(); }, [fetchHealth]);

  const handleReload = async () => {
    setReloading(true);
    try {
      const r = await apiFetch("/api/drm/reload", { method: "POST" });
      const d = await r.json();
      if (!r.ok) {
        showToast(await parseApiError(r, "CDM reload nije uspeo."), "error");
        return;
      }
      if (d.health) setHealth(d.health);
      showToast("CDM je ponovo učitan.", "success");
    } catch (e: unknown) {
      showToast(e instanceof Error ? e.message : "Mrežna greška.", "error");
    } finally {
      setReloading(false);
    }
  };

  const handleClearCache = async () => {
    setClearing(true);
    try {
      const r = await apiFetch("/api/drm/cache/clear", { method: "POST" });
      if (!r.ok) {
        showToast(await parseApiError(r, "Brisanje keša nije uspelo."), "error");
        return;
      }
      await fetchHealth();
      showToast("Key cache je očišćen.", "success");
    } catch (e: unknown) {
      showToast(e instanceof Error ? e.message : "Mrežna greška.", "error");
    } finally {
      setClearing(false);
    }
  };

  return (
    <div key="drm" className="tab-content tab-content-drm">
      <div className="tab-page-header tab-header-drm mb-6">
        <div
          className="tab-page-header-icon"
          style={{
            background: "linear-gradient(135deg,#7c3aed,#4f46e5)",
            boxShadow: "0 0 24px rgba(124,58,237,0.5)",
          }}
        >
          <Shield style={{ width: 26, height: 26, color: "white" }} />
        </div>
        <div style={{ flex: 1 }}>
          <h2 className="text-xl font-extrabold text-white mb-0.5 flex items-center gap-2">
            <Shield className="w-5 h-5 text-violet-400" /> DRM / Widevine Kontrolna Tabla
          </h2>
          <p className="text-xs text-text-muted">
            CDM dijagnostika, key cache, test licence i provider sertifikati
          </p>
        </div>
        <button
          type="button"
          onClick={() => setActiveTab("settings")}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold text-violet-300 border border-violet-500/30 bg-violet-500/10 hover:bg-violet-500/20 transition-all"
        >
          <Settings className="w-3.5 h-3.5" /> WVD u Postavkama
        </button>
        <button
          type="button"
          onClick={fetchHealth}
          disabled={loading}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold text-violet-300 border border-violet-500/30 bg-violet-500/10 hover:bg-violet-500/20 transition-all disabled:opacity-50"
        >
          {loading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <RefreshCw className="w-3.5 h-3.5" />}{" "}
          Osvježi
        </button>
      </div>

      <div className="drm-panel-grid">
        <div className="flex flex-col gap-5">
          <DrmCdmStatus health={health} loading={loading} reloading={reloading} onReload={handleReload} />
          <DrmKeyCache health={health} clearing={clearing} onClearCache={handleClearCache} />
          <DrmRecommendations recommendations={health?.recommendations ?? []} />
        </div>

        <div className="flex flex-col gap-5">
          <DrmTestKeys showToast={showToast} />
          <DrmCertPrefetch onHealthRefresh={fetchHealth} showToast={showToast} />
          <DrmSecurityLevels />
        </div>
      </div>
    </div>
  );
}
