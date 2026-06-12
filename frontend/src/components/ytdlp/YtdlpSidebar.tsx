import { Cookie, ExternalLink, Globe, Settings, ShieldAlert, Zap } from "lucide-react";
import type { AppStatus } from "../../types/app";
import { useAppShellSlice } from "../../context/appStore";

export interface YtdlpSidebarProps {
  status: AppStatus | null;
  cookiesConfigured: boolean;
}

export function YtdlpSidebar({ status, cookiesConfigured }: YtdlpSidebarProps) {
  const { setActiveTab } = useAppShellSlice();

  const ytdlpSvc = status?.services?.ytdlp;
  const ready = ytdlpSvc?.ready ?? ytdlpSvc?.authenticated ?? true;
  const ver = (ytdlpSvc as { ytdlp_version?: string } | undefined)?.ytdlp_version;
  const svcError = (ytdlpSvc as { error?: string } | undefined)?.error;

  const ffmpegOk = status?.binaries?.ffmpeg?.found ?? false;
  const aria2Ok = status?.binaries?.aria2c?.found ?? false;

  return (
    <div className="flex flex-col gap-6">
      <div className="glass-panel p-6 rounded-xl border border-glass glow-blue-card glow-card-premium">
        <h3 className="font-extrabold text-base mb-4 flex items-center gap-2 text-white">
          <Zap className="w-5 h-5 text-blue-400" />
          Status yt-dlp
        </h3>

        <div className="flex flex-col gap-3">
          <span
            className={`badge flex items-center gap-1.5 font-black px-2.5 py-1 text-[10px] tracking-wider rounded-md w-max ${
              ready
                ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-400"
                : "bg-amber-500/10 border-amber-500/30 text-amber-400"
            }`}
          >
            <span
              className={`w-1.5 h-1.5 rounded-full ${ready ? "bg-emerald-400" : "bg-amber-400"}`}
            />
            {ready ? (ver ? `yt-dlp ${ver}` : "Spremno") : svcError || "Proverite Node.js"}
          </span>

          <div className="flex flex-col gap-1.5 border-t border-white/[0.03] pt-3">
            <div className="flex justify-between items-center text-xs font-semibold text-white bg-black/10 p-2 rounded">
              <span className="text-text-secondary">FFmpeg:</span>
              <span className={ffmpegOk ? "text-emerald-400 font-black" : "text-red-400 font-black animate-pulse"}>
                {ffmpegOk ? "Pronađen" : "⚠️ Nije pronađen"}
              </span>
            </div>
            <div className="flex justify-between items-center text-xs font-semibold text-white bg-black/10 p-2 rounded">
              <span className="text-text-secondary">aria2c:</span>
              <span className={aria2Ok ? "text-emerald-400 font-black" : "text-text-muted font-black"}>
                {aria2Ok ? "Pronađen" : "Opciono"}
              </span>
            </div>
            <div className="flex justify-between items-center text-xs font-semibold text-white bg-black/10 p-2 rounded">
              <span className="text-text-secondary flex items-center gap-1">
                <Cookie className="w-3 h-3" /> Cookies:
              </span>
              <span
                className={
                  cookiesConfigured ? "text-emerald-400 font-black" : "text-amber-400 font-black animate-pulse"
                }
              >
                {cookiesConfigured ? "✓ Učitani" : "⚠️ Nisu učitani"}
              </span>
            </div>
          </div>

          {(!cookiesConfigured || !ffmpegOk) && (
            <div className="p-3 rounded-lg flex flex-col gap-2 text-xs border bg-amber-500/10 border-amber-500/20 text-amber-300">
              <div className="flex items-center gap-2 font-black">
                <ShieldAlert className="w-4 h-4 text-amber-400 shrink-0" />
                <span>VAŽNO UPOZORENJE</span>
              </div>
              <div className="flex flex-col gap-1.5 font-medium text-text-secondary leading-relaxed">
                {!ffmpegOk && (
                  <p>
                    • <strong className="text-red-400">FFmpeg nije pronađen!</strong> Bez njega preuzimanje i spajanje HD videa i zvuka neće raditi.
                  </p>
                )}
                {!cookiesConfigured && (
                  <p>
                    • <strong className="text-amber-400">Kolačići nisu učitani!</strong> YouTube i drugi servisi mogu blokirati preuzimanje (Bot detekcija).
                  </p>
                )}
              </div>
            </div>
          )}

          <button
            type="button"
            onClick={() => setActiveTab("settings")}
            className={`text-xs font-extrabold flex items-center justify-center gap-2 w-full mt-2 py-2 px-3 rounded-lg border transition-all ${
              !cookiesConfigured
                ? "bg-blue-600 hover:bg-blue-500 text-white border-blue-500 shadow-lg shadow-blue-500/20"
                : "text-blue-400 hover:underline border-transparent"
            }`}
          >
            <Settings className="w-3.5 h-3.5" />
            <span>{!cookiesConfigured ? "Podesi / Uvezi kolačiće" : "Postavke (yt-dlp, šablon imena)"}</span>
            <ExternalLink className="w-3 h-3 opacity-60" />
          </button>
        </div>
      </div>

      <div className="glass-panel p-6 rounded-xl border border-glass flex flex-col gap-4 glow-blue-card glow-card-premium">
        <h4 className="font-extrabold text-sm flex items-center gap-2 text-blue-400 border-b border-white/[0.04] pb-3">
          <ShieldAlert className="w-4 h-4" />
          Kako radi
        </h4>
        <p className="text-xs text-text-secondary leading-relaxed">
          Univerzalni preuzimač koristi yt-dlp za ekstrakciju sa hiljada sajtova. Izlaz je obično
          MP4/MKV sa ugrađenim metapodacima i titlovima.
        </p>
        <ul className="text-xs text-text-secondary flex flex-col gap-2 border-t border-white/[0.03] pt-3">
          <li className="flex items-start gap-2">
            <Globe className="w-3.5 h-3.5 text-blue-400 shrink-0 mt-0.5" />
            YouTube, X, TikTok, Vimeo, Facebook i ostali
          </li>
          <li>• Hardsub titlovi zahtevaju FFmpeg (Postavke → transcode)</li>
          <li>• Za privatne / geo-blokirane linkove: cookies ili proksi</li>
          <li>• DRM zaštićeni streamovi nisu podržani</li>
        </ul>
      </div>
    </div>
  );
}
