import {
  Download,
  Loader2,
  X,
  Zap,
} from "lucide-react";
import { useSnifferTab } from "../../hooks/domains/useSnifferTab";

export function SnifferToast() {
  const {
    applySniffedResource,
    downloadSnifferCapture,
    latestSniffed,
    setShowSnifferToast,
    showSnifferToast,
    sniffedItems,
    snifferDownloading,
    snifferReady,
  } = useSnifferTab();
  if (!showSnifferToast || !latestSniffed) return null;
  return (
  <div className={`fixed bottom-6 right-6 z-50 flex flex-col gap-3.5 p-5 rounded-xl glass-panel animate-slide max-w-sm w-96 border border-glass shadow-2xl ${
    latestSniffed.service === "hbomax" || latestSniffed.service === "hbo" ? "glow-purple-card border-purple-500/30" :
    latestSniffed.service === "voyo" ? "glow-orange-card border-orange-500/30" :
    latestSniffed.service === "rtsplaneta" || latestSniffed.service === "rts" ? "glow-rose-card border-rose-500/30" :
    latestSniffed.service === "eon" ? "glow-green-card border-green-500/30" :
    latestSniffed.service === "hrti" ? "glow-cyan-card border-cyan-500/30" : "glow-indigo"
  }`} style={{ background: "rgba(10, 11, 16, 0.95)", backdropFilter: "blur(16px)" }}>
    <div className="flex items-start justify-between">
      <div className="flex items-center gap-3">
        <div className={`w-10 h-10 rounded-lg flex items-center justify-center animate-pulse ${
          latestSniffed.service === "hbomax" || latestSniffed.service === "hbo" ? "bg-purple-600/20 text-purple-400" :
          latestSniffed.service === "voyo" ? "bg-orange-600/20 text-orange-400" :
          latestSniffed.service === "rtsplaneta" || latestSniffed.service === "rts" ? "bg-rose-600/20 text-rose-400" :
          latestSniffed.service === "eon" ? "bg-emerald-600/20 text-emerald-400" :
          latestSniffed.service === "hrti" ? "bg-cyan-600/20 text-cyan-400" : "bg-indigo-600/20 text-indigo-400"
        }`}>
          <Zap className="w-5 h-5" />
        </div>
        <div>
          <span className="text-[10px] uppercase font-black tracking-widest text-text-muted">
            Sniffer Aktivan
          </span>
          <h4 className="text-sm font-extrabold text-white">
            Presretnut {latestSniffed.service === "hbomax" || latestSniffed.service === "hbo" ? "HBO Max" :
                        latestSniffed.service === "voyo" ? "Voyo RS" :
                        latestSniffed.service === "rtsplaneta" || latestSniffed.service === "rts" ? "RTS Planeta" :
                        latestSniffed.service === "eon" ? "EON TV" :
                        latestSniffed.service === "hrti" ? "HRTi" : latestSniffed.service} resurs
          </h4>
        </div>
      </div>
      <button
        onClick={() => setShowSnifferToast(false)}
        className="text-text-muted hover:text-white transition-colors"
      >
        <X className="w-4 h-4" />
      </button>
    </div>

    <div className="text-xs bg-white/[0.03] border border-white/[0.06] rounded-lg p-3 flex flex-col gap-1.5 font-mono break-all text-text-secondary">
      <div>
        <span className="text-text-muted">Tip:</span>{" "}
        <span className="text-white font-bold">
          {latestSniffed.type === "ready"
            ? "✅ Manifest + License spremni"
            : latestSniffed.type === "manifest"
              ? "📄 Manifest (.mpd/.m3u8)"
              : "🔑 Widevine License"}
        </span>
      </div>
      {sniffedItems[latestSniffed.service]?.manifestUrl && (
        <div className="line-clamp-2 text-[11px]">
          <span className="text-text-muted">MPD:</span> {sniffedItems[latestSniffed.service]?.manifestUrl}
        </div>
      )}
      {sniffedItems[latestSniffed.service]?.licenseUrl && (
        <div className="line-clamp-2 text-[11px]">
          <span className="text-text-muted">Lic:</span> {sniffedItems[latestSniffed.service]?.licenseUrl}
        </div>
      )}
      {!sniffedItems[latestSniffed.service]?.manifestUrl && (
        <div className="line-clamp-2 max-h-12 overflow-hidden text-[11px]">
          <span className="text-text-muted">URL:</span> {latestSniffed.url}
        </div>
      )}
    </div>

    <div className="flex gap-2 flex-wrap">
      {(snifferReady[latestSniffed.service]?.ready ||
        (sniffedItems[latestSniffed.service]?.manifestUrl &&
          sniffedItems[latestSniffed.service]?.licenseUrl)) && (
        <button
          onClick={() => downloadSnifferCapture(latestSniffed.service)}
          disabled={snifferDownloading === latestSniffed.service}
          className="flex-1 py-2 px-3 rounded-lg text-xs font-bold text-white flex items-center justify-center gap-1.5 bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 shadow-lg min-w-[140px]"
        >
          {snifferDownloading === latestSniffed.service ? (
            <Loader2 className="w-3.5 h-3.5 animate-spin" />
          ) : (
            <Download className="w-3.5 h-3.5" />
          )}
          Preuzmi odmah
        </button>
      )}
      <button
        onClick={() => applySniffedResource(latestSniffed.service)}
        className={`flex-1 py-2 px-3 rounded-lg text-xs font-bold text-white flex items-center justify-center gap-1.5 transition-all shadow-lg hover:shadow-xl min-w-[120px] ${
          latestSniffed.service === "hbomax" || latestSniffed.service === "hbo" ? "bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 shadow-purple-500/20" :
          latestSniffed.service === "voyo" ? "bg-gradient-to-r from-orange-600 to-amber-600 hover:from-orange-500 hover:to-amber-500 shadow-orange-500/20" :
          latestSniffed.service === "rtsplaneta" || latestSniffed.service === "rts" ? "bg-gradient-to-r from-rose-600 to-pink-600 hover:from-rose-500 hover:to-pink-500 shadow-rose-500/20" :
          latestSniffed.service === "eon" ? "bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 shadow-emerald-500/20" :
          latestSniffed.service === "hrti" ? "bg-gradient-to-r from-cyan-600 to-teal-600 hover:from-cyan-500 hover:to-teal-500 shadow-cyan-500/20" : "bg-indigo-600"
        }`}
      >
        <Zap className="w-3.5 h-3.5" /> Popuni polja
      </button>
      <button
        onClick={() => setShowSnifferToast(false)}
        className="py-2 px-3 rounded-lg text-xs font-bold bg-white/[0.05] border border-white/[0.08] hover:bg-white/[0.1] text-white transition-colors"
      >
        Ignoriši
      </button>
    </div>
  </div>
  );
}
