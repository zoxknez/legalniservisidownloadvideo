import { Shield, ExternalLink } from "lucide-react";
import type { DrmStatusSummary } from "../../types/app";

interface SettingsDrmCardProps {
  drm?: DrmStatusSummary | null;
  onOpenDrmTab: () => void;
}

export function SettingsDrmCard({ drm, onOpenDrmTab }: SettingsDrmCardProps) {
  const ready = Boolean(drm?.cdm_ready);
  return (
    <div className="glass-panel p-5 rounded-xl border border-glass flex flex-col gap-3 glow-violet-card glow-card-premium">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <h3 className="font-extrabold text-base text-white flex items-center gap-2">
          <Shield className="w-4 h-4 text-violet-400" />
          Widevine CDM
        </h3>
        <span
          className={`text-[10px] font-bold px-2 py-0.5 rounded border ${
            ready
              ? "text-emerald-400 border-emerald-500/30 bg-emerald-500/10"
              : "text-red-400 border-red-500/30 bg-red-500/10"
          }`}
        >
          {ready ? "CDM spreman" : "CDM nedostaje"}
        </span>
      </div>
      <p className="text-xs text-text-secondary m-0 leading-relaxed">
        {ready
          ? `Nivo: ${drm?.security_level_name || "—"}. Keš ključeva: ${drm?.key_cache_alive ?? 0} aktivnih unosa.`
          : "Instalirajte device.wvd u panelu ispod ili na DRM tabu."}
      </p>
      {drm?.wvd_file && (
        <p className="text-[10px] font-mono text-text-muted m-0 truncate" title={drm.wvd_file}>
          {drm.wvd_file}
        </p>
      )}
      <button
        type="button"
        onClick={onOpenDrmTab}
        className="self-start flex items-center gap-1.5 text-xs font-bold text-violet-300 hover:text-violet-200"
      >
        <ExternalLink className="w-3.5 h-3.5" />
        Otvori DRM kontrolnu tablu
      </button>
    </div>
  );
}
