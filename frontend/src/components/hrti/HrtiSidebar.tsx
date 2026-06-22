import { Check, ExternalLink, HardDrive, Settings, ShieldAlert, User } from "lucide-react";
import type { AppStatus } from "../../types/app";
import { useAppShellSlice } from "../../context/appStore";

export function HrtiSidebar({
  status,
  authenticated,
}: {
  status: AppStatus | null;
  authenticated: boolean;
}) {
  const { setActiveTab } = useAppShellSlice();
  const cdmReady = status?.drm?.cdm_ready ?? status?.binaries?.device_wvd?.found ?? false;
  const wvdPath = status?.binaries?.device_wvd?.path || status?.drm?.wvd_file || "";
  const ffmpegOk = status?.binaries?.ffmpeg?.found ?? false;

  return (
    <div className="flex flex-col gap-6">
      <div className="glass-panel p-6 rounded-xl border border-glass glow-cyan-card glow-card-premium">
        <h3 className="font-extrabold text-base mb-4 flex items-center gap-2 text-white">
          <User className="w-5 h-5 text-cyan-400" />
          Status naloga
        </h3>

        {authenticated ? (
          <div className="flex flex-col gap-3">
            <span className="badge flex items-center gap-1.5 bg-emerald-500/10 border-emerald-500/30 text-emerald-400 font-black px-2.5 py-1 text-[10px] tracking-wider rounded-md w-max">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
              Prijavljen
            </span>
            {status?.services?.hrti?.email && (
              <div className="flex flex-col gap-1.5 border-t border-white/[0.03] pt-3">
                <p className="text-xs font-bold text-text-secondary">E-mail:</p>
                <p className="text-sm font-semibold text-white truncate bg-black/20 p-2 rounded border border-white/[0.02]">
                  {status.services.hrti.email}
                </p>
              </div>
            )}
          </div>
        ) : (
          <div className="flex flex-col gap-3">
            <span className="badge flex items-center gap-1.5 bg-red-500/10 border-red-500/30 text-red-400 font-black px-2.5 py-1 text-[10px] tracking-wider rounded-md w-max">
              Nije prijavljen
            </span>
            <p className="text-xs text-text-secondary leading-relaxed">
              Prijavite se u Postavkama sa HRTi nalogom da biste pristupili katalogu i Widevine preuzimanju.
            </p>
            <button
              type="button"
              onClick={() => setActiveTab("settings")}
              className="text-xs font-bold text-cyan-400 flex items-center gap-1.5 hover:underline w-max"
            >
              <Settings className="w-3.5 h-3.5" /> Otvori Postavke
              <ExternalLink className="w-3 h-3 opacity-60" />
            </button>
          </div>
        )}
      </div>

      <div className="glass-panel p-6 rounded-xl border border-glass flex flex-col gap-4 glow-cyan-card glow-card-premium">
        <h4 className="font-extrabold text-sm flex items-center gap-2 text-cyan-400 border-b border-white/[0.04] pb-3">
          <HardDrive className="w-4 h-4" />
          Widevine & alati
        </h4>
        <div className="flex flex-col gap-2 text-xs">
          <div className="flex justify-between items-center bg-black/10 p-2 rounded">
            <span className="text-text-secondary">device.wvd (L3)</span>
            <span className={cdmReady ? "text-emerald-400 font-black" : "text-amber-400 font-black"}>
              {cdmReady ? "Spremno" : "Nedostaje"}
            </span>
          </div>
          <div className="flex justify-between items-center bg-black/10 p-2 rounded">
            <span className="text-text-secondary">FFmpeg</span>
            <span className={ffmpegOk ? "text-emerald-400 font-black" : "text-amber-400 font-black"}>
              {ffmpegOk ? "Pronađen" : "Nedostaje"}
            </span>
          </div>
        </div>
        {wvdPath && (
          <p className="text-[10px] text-text-muted font-mono break-all">{wvdPath}</p>
        )}
        {!cdmReady && (
          <button
            type="button"
            onClick={() => setActiveTab("settings")}
            className="text-xs font-bold text-cyan-400 flex items-center gap-1.5 hover:underline w-max"
          >
            <Settings className="w-3.5 h-3.5" /> Postavke / DRM tab
          </button>
        )}
      </div>

      <div className="glass-panel p-6 rounded-xl border border-glass flex flex-col gap-4 glow-cyan-card glow-card-premium">
        <h4 className="font-extrabold text-sm flex items-center gap-2 text-cyan-400 border-b border-white/[0.04] pb-3">
          <ShieldAlert className="w-4 h-4" />
          Kako radi
        </h4>
        <p className="text-xs text-text-secondary leading-relaxed">
          HRTi koristi Widevine L3 (DRMtoday). Potrebni su hrvatski IP, nalog na hrti.hrt.hr i validan{" "}
          <code className="text-cyan-300">device.wvd</code>.
        </p>
        <ul className="text-xs text-text-secondary flex flex-col gap-2 border-t border-white/[0.03] pt-3">
          <li className="flex items-start gap-2">
            <Check className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
            Katalog: filmovi, serije, pretraga po naslovu
          </li>
          <li className="flex items-start gap-2">
            <Check className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
            Serije: batch preuzimanje epizoda po sezonama
          </li>
          <li className="flex items-start gap-2">
            <Check className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
            Izlaz: MP4 ili MKV prema globalnoj postavci formata
          </li>
        </ul>
      </div>
    </div>
  );
}
