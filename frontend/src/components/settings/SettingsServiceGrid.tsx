import { Film, Play, Radio, Tv, Zap } from "lucide-react";
import type { AppStatus } from "../../types/app";

const SERVICES = [
  { key: "voyo", label: "Voyo", icon: Tv, color: "service-voyo", authKey: "authenticated" as const },
  { key: "hrti", label: "HRTi", icon: Film, color: "service-hrti", authKey: "authenticated" as const },
  { key: "eon", label: "EON TV", icon: Play, color: "service-eon", authKey: "ready" as const },
  { key: "rtsplaneta", label: "RTS Planeta", icon: Radio, color: "service-rts", authKey: "authenticated" as const },
  { key: "hbomax", label: "HBO Max", icon: Zap, color: "service-hbo", authKey: "authenticated" as const },
] as const;

interface SettingsServiceGridProps {
  status: AppStatus;
}

export function SettingsServiceGrid({ status }: SettingsServiceGridProps) {
  return (
    <div className="service-status-grid">
      {SERVICES.map(({ key, label, icon: Icon, color, authKey }) => {
        const serviceStatus = status.services[key];
        const auth = Boolean(
          authKey === "ready" ? serviceStatus?.ready : serviceStatus?.authenticated,
        );
        const err = serviceStatus?.error;
        const hint =
          key === "hbomax" && !auth
            ? "Uvoz sesije, bookmarklet ili device login"
            : key === "eon" && !auth
              ? "Uređaj + kolačići ili auto-sync"
              : key === "voyo" && auth
                ? "AES-128 HLS (bez Widevine)"
                : undefined;

        return (
          <div
            key={key}
            className={`service-status-card ${auth ? "authenticated" : "not-authenticated"}`}
          >
            <Icon className={`w-5 h-5 ${color}`} />
            <span className="text-xs font-bold text-white">{label}</span>
            <span className={`text-[10px] font-semibold ${auth ? "text-emerald-400" : "text-red-400"}`}>
              {auth ? "Spreman" : "Nije spreman"}
            </span>
            {hint && !auth && (
              <span className="text-[9px] text-text-muted text-center leading-tight">{hint}</span>
            )}
            {err && !auth && (
              <span className="text-[9px] text-amber-400/90 text-center leading-tight line-clamp-2" title={err}>
                {err}
              </span>
            )}
          </div>
        );
      })}
    </div>
  );
}
