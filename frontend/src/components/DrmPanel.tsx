import { useState, useEffect, useCallback } from "react";
import {
  Shield, ShieldCheck, KeyRound, RefreshCw, Trash2, FlaskConical,
  Loader2, Copy, Check, Info, Database, AlertTriangle,
  CheckCircle2, AlertCircle, RotateCcw, ChevronRight, Lock, Download,
} from "lucide-react";
import { apiFetch } from "../lib/api";
import type { DrmHealth } from "../types/app";

export function DrmPanel() {
  const [health, setHealth] = useState<DrmHealth | null>(null);
  const [loading, setLoading] = useState(false);
  const [reloading, setReloading] = useState(false);
  const [clearing, setClearing] = useState(false);
  const [testMpdUrl, setTestMpdUrl] = useState("");
  const [testLicUrl, setTestLicUrl] = useState("");
  const [testService, setTestService] = useState("manual");
  const [testResult, setTestResult] = useState<{keys?: string[]; psshs?: string[]; error?: string} | null>(null);
  const [testing, setTesting] = useState(false);
  const [prefetchLicUrl, setPrefetchLicUrl] = useState("");
  const [prefetchService, setPrefetchService] = useState("hrti");
  const [prefetching, setPrefetching] = useState(false);
  const [prefetchMsg, setPrefetchMsg] = useState<string | null>(null);
  const [copiedKey, setCopiedKey] = useState<string | null>(null);

  const fetchHealth = useCallback(async () => {
    setLoading(true);
    try {
      const r = await apiFetch("/api/drm/health");
      const d = await r.json();
      setHealth(d);
    } catch { /* ignore */ }
    setLoading(false);
  }, []);

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

  const handleTestKeys = async () => {
    if (!testMpdUrl || !testLicUrl) return;
    setTesting(true);
    setTestResult(null);
    try {
      const r = await apiFetch("/api/drm/test-keys", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mpd_url: testMpdUrl, license_url: testLicUrl, service: testService })
      });
      const d = await r.json();
      if (r.ok && d.success) {
        setTestResult({ keys: d.keys, psshs: d.psshs });
      } else {
        setTestResult({ error: d.detail || "Nepoznata greška" });
      }
    } catch (e: unknown) {
      setTestResult({ error: e instanceof Error ? e.message : "Network error" });
    }
    setTesting(false);
  };

  const handlePrefetchCert = async () => {
    if (!prefetchLicUrl) return;
    setPrefetching(true);
    setPrefetchMsg(null);
    try {
      const r = await apiFetch("/api/drm/prefetch-cert", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ service: prefetchService, license_url: prefetchLicUrl })
      });
      const d = await r.json();
      setPrefetchMsg(d.message || (d.success ? "Uspješno!" : "Neuspješno"));
      await fetchHealth();
    } catch (e: unknown) {
      setPrefetchMsg(e instanceof Error ? e.message : "Network error");
    }
    setPrefetching(false);
  };

  const copyKey = (key: string) => {
    navigator.clipboard.writeText(key);
    setCopiedKey(key);
    setTimeout(() => setCopiedKey(null), 1500);
  };

  const sl = health?.wvd_metadata?.security_level ?? 0;
  const slColor = sl === 1 ? "#10b981" : sl === 2 ? "#f59e0b" : sl === 3 ? "#6366f1" : "#64748b";
  const slBg = sl === 1 ? "rgba(16,185,129,0.12)" : sl === 2 ? "rgba(245,158,11,0.12)" : sl === 3 ? "rgba(99,102,241,0.12)" : "rgba(100,116,139,0.12)";

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

          {/* CDM Status Card */}
          <div className="glass-panel p-5 rounded-xl border border-glass relative overflow-hidden">
            <div className="console-scanline" />
            <h3 className="text-sm font-bold text-white mb-4 flex items-center gap-2">
              <ShieldCheck className="w-4 h-4 text-violet-400" /> CDM Status
            </h3>
            {loading && !health ? (
              <div className="flex items-center gap-2 text-text-muted text-xs"><Loader2 className="w-4 h-4 animate-spin" /> Učitavanje...</div>
            ) : health ? (
              <div className="flex flex-col gap-3">
                {/* Ready badge */}
                <div className="flex items-center gap-2">
                  {health.cdm_ready ? (
                    <span className="flex items-center gap-1.5 text-xs font-bold text-emerald-400 bg-emerald-500/10 border border-emerald-500/25 px-2.5 py-1 rounded-full">
                      <CheckCircle2 className="w-3.5 h-3.5" /> CDM Spreman
                    </span>
                  ) : (
                    <span className="flex items-center gap-1.5 text-xs font-bold text-red-400 bg-red-500/10 border border-red-500/25 px-2.5 py-1 rounded-full">
                      <AlertCircle className="w-3.5 h-3.5" /> CDM Nije Spreman
                    </span>
                  )}
                  {health.legacy_mode && (
                    <span className="text-xs text-amber-400 bg-amber-500/10 border border-amber-500/20 px-2 py-0.5 rounded-full font-semibold">Legacy Mode</span>
                  )}
                </div>

                {/* Security Level */}
                {health.wvd_metadata.is_valid && (
                  <div className="rounded-xl p-3 border" style={{background: slBg, borderColor: slColor + "40"}}>
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-xs text-text-muted font-semibold">Security Level</span>
                      <span className="text-xs font-extrabold" style={{color: slColor}}>
                        L{health.wvd_metadata.security_level ?? "?"}
                      </span>
                    </div>
                    <p className="text-xs font-bold" style={{color: slColor}}>
                      {health.wvd_metadata.security_level_name}
                    </p>
                    {sl === 3 && (
                      <p className="text-[10px] text-text-muted mt-1">
                        Software CDM – dovoljno za 1080p/SDR. L1 zahtijeva hardverski TEE čip.
                      </p>
                    )}
                    {sl === 1 && (
                      <p className="text-[10px] text-text-muted mt-1">
                        Hardverski zaštićen – maksimalna razina zaštite sadržaja.
                      </p>
                    )}
                  </div>
                )}

                {/* WVD Metadata */}
                <div className="flex flex-col gap-1.5 text-xs">
                  {[
                    ["Tip uređaja", health.wvd_metadata.device_type ?? "—"],
                    ["WVD verzija", health.wvd_metadata.wvd_version != null ? `v${health.wvd_metadata.wvd_version}` : "—"],
                    ["Veličina fajla", health.wvd_metadata.file_size ? `${health.wvd_metadata.file_size.toLocaleString()} B` : "—"],
                    ["Private key", health.wvd_metadata.private_key_size > 0 ? `${health.wvd_metadata.private_key_size * 8}-bit RSA` : "—"],
                    ["Client ID", health.wvd_metadata.client_id_size > 0 ? `${health.wvd_metadata.client_id_size} B` : "—"],
                    ["pywidevine", health.pywidevine_version ?? "—"],
                  ].map(([label, val]) => (
                    <div key={label} className="flex justify-between items-center py-0.5 border-b border-white/[0.04]">
                      <span className="text-text-muted">{label}:</span>
                      <span className="font-mono text-white text-[11px]">{val}</span>
                    </div>
                  ))}
                  <div className="flex justify-between items-center py-0.5">
                    <span className="text-text-muted">WVD putanja:</span>
                    <span className="font-mono text-violet-300 text-[10px] max-w-[180px] truncate" title={health.wvd_file ?? "—"}>
                      {health.wvd_file ? health.wvd_file.split(/[\\/]/).pop() : "—"}
                    </span>
                  </div>
                </div>

                {/* Error */}
                {health.wvd_metadata.error && (
                  <div className="flex items-start gap-2 bg-red-500/10 border border-red-500/20 rounded-lg p-2.5 text-xs text-red-300">
                    <AlertCircle className="w-3.5 h-3.5 flex-shrink-0 mt-0.5" />
                    <span>{health.wvd_metadata.error}</span>
                  </div>
                )}

                {/* Reload CDM button */}
                <button onClick={handleReload} disabled={reloading}
                  className="w-full flex items-center justify-center gap-2 py-2 rounded-lg text-xs font-bold text-violet-300 border border-violet-500/30 bg-violet-500/10 hover:bg-violet-500/20 transition-all disabled:opacity-50">
                  {reloading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <RotateCcw className="w-3.5 h-3.5" />}
                  Reload CDM (novi device.wvd)
                </button>
              </div>
            ) : (
              <p className="text-xs text-text-muted">Podaci nisu dostupni.</p>
            )}
          </div>

          {/* Key Cache Card */}
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
                <button onClick={handleClearCache} disabled={clearing || health.key_cache.total_entries === 0}
                  className="flex items-center justify-center gap-2 py-2 rounded-lg text-xs font-bold text-red-300 border border-red-500/20 bg-red-500/5 hover:bg-red-500/15 transition-all disabled:opacity-40">
                  {clearing ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Trash2 className="w-3.5 h-3.5" />}
                  Očisti Cache
                </button>

                {/* Provider certs */}
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

          {/* Recommendations */}
          {health?.recommendations && health.recommendations.length > 0 && (
            <div className="glass-panel p-5 rounded-xl border border-amber-500/20 bg-amber-500/5">
              <h3 className="text-sm font-bold text-amber-300 mb-3 flex items-center gap-2">
                <AlertTriangle className="w-4 h-4" /> Preporuke
              </h3>
              <ul className="flex flex-col gap-2">
                {health.recommendations.map((r, i) => (
                  <li key={i} className="flex items-start gap-2 text-xs text-amber-200/80">
                    <ChevronRight className="w-3.5 h-3.5 flex-shrink-0 mt-0.5 text-amber-400" />
                    {r}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>

        {/* RIGHT COL */}
        <div className="flex flex-col gap-5">

          {/* Test Keys Form */}
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
                  {["manual","hrti","eon","voyo","rtsplaneta","hbomax"].map(s => (
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
                            <button onClick={() => copyKey(key)}
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

          {/* Provider Cert Prefetch */}
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

          {/* L1 vs L3 Explanation */}
          <div className="glass-panel p-5 rounded-xl border border-glass">
            <h3 className="text-sm font-bold text-white mb-3 flex items-center gap-2">
              <Info className="w-4 h-4 text-slate-400" /> L1 vs L3 – Objašnjenje
            </h3>
            <div className="flex flex-col gap-2 text-[11px] text-text-muted leading-relaxed">
              {[
                {level:"L1",color:"#10b981",desc:"Widevine se izvršava u hardverskom TEE (Trusted Execution Environment). Ključevi nikad ne napuštaju sigurni čip. Podržava 4K HDR streams. Zahtijeva certifikovani uređaj (Android TEE, Qualcomm SPE...)."},
                {level:"L2",color:"#f59e0b",desc:"Kriptografija u TEE, ali dekodiranje može biti u softveru. Rijetko korišten, prelazni nivo."},
                {level:"L3",color:"#6366f1",desc:"Potpuno softverski CDM – pokreće se u user-space procesu. Dostupan na svim PC-evima. Ograničen na 1080p/SDR za većinu servisa. Keybox je zaštićen softverski."},
              ].map(({level,color,desc}) => (
                <div key={level} className="rounded-lg p-2.5 border" style={{background:`${color}0d`,borderColor:`${color}30`}}>
                  <span className="font-extrabold text-xs" style={{color}}>{level}  </span>
                  {desc}
                </div>
              ))}
            </div>
          </div>

        </div>
      </div>
    </div>
  );
}
