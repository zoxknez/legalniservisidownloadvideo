import { useState } from "react";
import { Lock, Loader2, Download } from "lucide-react";
import { apiFetch } from "../../lib/api";

interface DrmCertPrefetchProps {
  onHealthRefresh: () => void;
}

export function DrmCertPrefetch({ onHealthRefresh }: DrmCertPrefetchProps) {
  const [prefetchLicUrl, setPrefetchLicUrl] = useState("");
  const [prefetchService, setPrefetchService] = useState("hrti");
  const [prefetching, setPrefetching] = useState(false);
  const [prefetchMsg, setPrefetchMsg] = useState<string | null>(null);

  const handlePrefetchCert = async () => {
    if (!prefetchLicUrl) return;
    setPrefetching(true);
    setPrefetchMsg(null);
    try {
      const r = await apiFetch("/api/drm/prefetch-cert", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ service: prefetchService, license_url: prefetchLicUrl }),
      });
      const d = await r.json();
      setPrefetchMsg(d.message || (d.success ? "Uspješno!" : "Neuspješno"));
      onHealthRefresh();
    } catch (e: unknown) {
      setPrefetchMsg(e instanceof Error ? e.message : "Network error");
    }
    setPrefetching(false);
  };

  return (
    <div className="glass-panel p-5 rounded-xl border border-glass">
      <h3 className="text-sm font-bold text-white mb-1 flex items-center gap-2">
        <Lock className="w-4 h-4 text-blue-400" /> Provider Sertifikat Prefetch
      </h3>
      <p className="text-[10px] text-text-muted mb-4">
        Šifruje Client ID u license requestu za bolju privatnost i ponekad zaobilazi strože server provjere.
      </p>
      <div className="flex flex-col gap-3">
        <div>
          <label className="text-[11px] font-semibold text-text-muted uppercase tracking-wide block mb-1">Servis</label>
          <select
            value={prefetchService} onChange={e => setPrefetchService(e.target.value)}
            className="w-full bg-white/[0.04] border border-white/[0.1] rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-blue-500/50"
            style={{backgroundColor:"rgba(255,255,255,0.04)"}}>
            {["hrti","eon","voyo","rtsplaneta","hbomax","manual"].map(s => (
              <option key={s} value={s} style={{background:"#1a1a2e"}}>{s}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="text-[11px] font-semibold text-text-muted uppercase tracking-wide block mb-1">License URL</label>
          <input
            value={prefetchLicUrl} onChange={e => setPrefetchLicUrl(e.target.value)}
            placeholder="https://lic.drmtoday.com/license-proxy-widevine/cenc/"
            className="w-full bg-white/[0.04] border border-white/[0.1] rounded-lg px-3 py-2 text-xs text-white placeholder-text-muted focus:outline-none focus:border-blue-500/50 transition-all"
          />
        </div>
        <button onClick={handlePrefetchCert} disabled={prefetching || !prefetchLicUrl}
          className="flex items-center justify-center gap-2 py-2.5 rounded-lg text-xs font-bold text-white border border-blue-500/40 transition-all disabled:opacity-40"
          style={{background:"linear-gradient(135deg,rgba(59,130,246,0.4),rgba(37,99,235,0.3))"}}>
          {prefetching ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Download className="w-3.5 h-3.5" />}
          {prefetching ? "Preuzimam..." : "Preuzmi Provider Sertifikat"}
        </button>
        {prefetchMsg && (
          <div className={`rounded-lg p-2.5 text-xs border ${prefetchMsg.includes("Uspješno") || prefetchMsg.includes("preuzet") ? "bg-emerald-500/10 border-emerald-500/20 text-emerald-300" : "bg-amber-500/10 border-amber-500/20 text-amber-300"}`}>
            {prefetchMsg}
          </div>
        )}
      </div>
    </div>
  );
}
