import { useState } from "react";
import {
  FlaskConical, KeyRound, Loader2, Copy, Check,
  CheckCircle2, AlertCircle,
} from "lucide-react";
import { apiFetch, parseApiError } from "../../lib/api";
import type { ShowToastFn } from "../../hooks/domainTypes";

interface DrmTestKeysProps {
  showToast: ShowToastFn;
}

export function DrmTestKeys({ showToast }: DrmTestKeysProps) {
  const [testMpdUrl, setTestMpdUrl] = useState("");
  const [testLicUrl, setTestLicUrl] = useState("");
  const [testService, setTestService] = useState("manual");
  const [testResult, setTestResult] = useState<{keys?: string[]; psshs?: string[]; error?: string} | null>(null);
  const [testing, setTesting] = useState(false);
  const [copiedKey, setCopiedKey] = useState<string | null>(null);

  const handleTestKeys = async () => {
    if (!testMpdUrl || !testLicUrl) return;
    setTesting(true);
    setTestResult(null);
    try {
      const r = await apiFetch("/api/drm/test-keys", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mpd_url: testMpdUrl, license_url: testLicUrl, service: testService }),
      });
      const d = await r.json();
      if (r.ok && d.success) {
        setTestResult({ keys: d.keys, psshs: d.psshs });
        showToast(`Pronađeno ${d.keys?.length ?? 0} ključeva.`, "success");
      } else {
        const msg =
          r.status === 403
            ? "Izvoz ključeva je onemogućen. Postavite VIDEODOWNLOAD_ALLOW_DRM_KEY_EXPORT=true za dijagnostiku."
            : await parseApiError(r, d.detail || "Nepoznata greška");
        setTestResult({ error: msg });
        showToast(msg, "error");
      }
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Mrežna greška";
      setTestResult({ error: msg });
      showToast(msg, "error");
    }
    setTesting(false);
  };

  const copyKey = (key: string) => {
    navigator.clipboard.writeText(key);
    setCopiedKey(key);
    setTimeout(() => setCopiedKey(null), 1500);
  };

  return (
    <div className="glass-panel p-5 rounded-xl border border-glass relative overflow-hidden">
      <div className="console-scanline" />
      <h3 className="text-sm font-bold text-white mb-4 flex items-center gap-2">
        <FlaskConical className="w-4 h-4 text-emerald-400" /> Test License / Dekriptovani Ključevi
      </h3>
      <div className="flex flex-col gap-3">
        <div>
          <label className="text-[11px] font-semibold text-text-muted uppercase tracking-wide block mb-1">MPD Manifest URL</label>
          <input
            value={testMpdUrl} onChange={e => setTestMpdUrl(e.target.value)}
            placeholder="https://example.com/manifest.mpd"
            className="w-full bg-white/[0.04] border border-white/[0.1] rounded-lg px-3 py-2 text-xs text-white placeholder-text-muted focus:outline-none focus:border-violet-500/50 transition-all"
          />
        </div>
        <div>
          <label className="text-[11px] font-semibold text-text-muted uppercase tracking-wide block mb-1">License URL</label>
          <input
            value={testLicUrl} onChange={e => setTestLicUrl(e.target.value)}
            placeholder="https://lic.drmtoday.com/license-proxy-widevine/cenc/"
            className="w-full bg-white/[0.04] border border-white/[0.1] rounded-lg px-3 py-2 text-xs text-white placeholder-text-muted focus:outline-none focus:border-violet-500/50 transition-all"
          />
        </div>
        <div>
          <label className="text-[11px] font-semibold text-text-muted uppercase tracking-wide block mb-1">Servis</label>
          <select
            value={testService} onChange={e => setTestService(e.target.value)}
            className="w-full bg-white/[0.04] border border-white/[0.1] rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-violet-500/50"
            style={{backgroundColor:"rgba(255,255,255,0.04)"}}>
            {["manual","hrti","eon","rtsplaneta","hbomax"].map(s => (
              <option key={s} value={s} style={{background:"#1a1a2e"}}>{s}</option>
            ))}
          </select>
        </div>
        <button onClick={handleTestKeys} disabled={testing || !testMpdUrl || !testLicUrl}
          className="w-full flex items-center justify-center gap-2 py-2.5 rounded-lg text-xs font-bold text-white border border-violet-500/40 transition-all disabled:opacity-40"
          style={{background:"linear-gradient(135deg,rgba(124,58,237,0.5),rgba(79,70,229,0.4))"}}>
          {testing ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <KeyRound className="w-3.5 h-3.5" />}
          {testing ? "Dohvaćam ključeve..." : "Dohvati Ključeve"}
        </button>

        {testResult && (
          <div className={`rounded-xl p-3 border text-xs ${testResult.error ? "bg-red-500/10 border-red-500/20" : "bg-emerald-500/10 border-emerald-500/20"}`}>
            {testResult.error ? (
              <div className="flex items-start gap-2 text-red-300">
                <AlertCircle className="w-4 h-4 flex-shrink-0" />
                <span>{testResult.error}</span>
              </div>
            ) : (
              <div className="flex flex-col gap-2">
                <p className="font-bold text-emerald-400 flex items-center gap-1.5">
                  <CheckCircle2 className="w-3.5 h-3.5" />
                  {testResult.keys?.length} ključ(eva) pronađeno  ·  {testResult.psshs?.length} PSSH
                </p>
                <div className="flex flex-col gap-1 mt-1">
                  {testResult.keys?.map(key => (
                    <div key={key} className="flex items-center gap-2 bg-white/[0.04] rounded-lg px-2.5 py-1.5 group">
                      <span className="font-mono text-[10px] text-white flex-1 break-all">{key}</span>
                      <button type="button" onClick={() => copyKey(key)}
                        className="opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0">
                        {copiedKey === key ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3 text-text-muted hover:text-white" />}
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
