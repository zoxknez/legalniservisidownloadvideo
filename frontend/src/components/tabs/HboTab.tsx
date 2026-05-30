import {
  Check,
  Clapperboard,
  Download,
  FileText,
  Film,
  Globe,
  Info,
  Lock,
  ShieldAlert,
  User,
  Zap,
} from "lucide-react";
import { CustomSelect } from "../CustomSelect";
import { useHboTab } from "../../hooks/domains/useHboTab";
import { cssVars } from "../../utils/cssVars";

export function HboTab() {
  const {
    hboDirectMode,
    hboDirectSubs,
    hboDirectTitle,
    hboLicenseUrl,
    hboManifestUrl,
    hboMarket,
    hboSubs,
    hboTarget,
    setHboDirectMode,
    setHboDirectSubs,
    setHboDirectTitle,
    setHboLicenseUrl,
    setHboManifestUrl,
    setHboMarket,
    setHboSubs,
    setHboTarget,
    startHboDirectDownload,
    startHboDownload,
    startHboLogin,
    status,
  } = useHboTab();
  return (
<div key="hbo" className="tab-content tab-content-hbo">
    <div className="tab-page-header tab-header-hbo mb-6">
      <div className="tab-page-header-icon animate-pulse" style={{background:"linear-gradient(135deg,#9333ea,#7e22ce)"}}>
        <Clapperboard style={{width:24,height:24,color:"white"}} />
      </div>
      <div style={{flex:1}}>
        <div className="flex items-center justify-between flex-wrap gap-2">
          <h2 className="text-2xl font-extrabold text-white mb-1 flex items-center gap-2.5">
            <Clapperboard className="w-6 h-6 text-purple-400" /> HBO Max
          </h2>
          <span className="badge flex items-center gap-1.5 bg-purple-500/10 border-purple-500/30 text-purple-400 font-black px-2.5 py-1 text-[10px] tracking-wider rounded-md">
            <Lock className="w-3.5 h-3.5" /> WIDEVINE L3 DEKRIPCIJA AKTIVNA
          </span>
        </div>
        <p className="text-text-secondary text-sm">Prijava uređaja, preuzimanje po Video ID-u, ili Bypass Mode sa direktnim MPD/License URL-ovima.</p>
      </div>
    </div>

    {/* Mode Toggle */}
    <div className="sliding-tabs-wrapper mb-6">
      <div
        className="sliding-tabs-slider"
        style={{
          width: "calc(50% - 4px)",
          transform: `translateX(${!hboDirectMode ? "0%" : "100%"})`
        }}
      />
      <button
        type="button"
        onClick={() => setHboDirectMode(false)}
        className={`sliding-tabs-btn ${!hboDirectMode ? "active" : ""}`}
      >
        Standardno (Login + ID)
      </button>
      <button
        type="button"
        onClick={() => setHboDirectMode(true)}
        className={`sliding-tabs-btn ${hboDirectMode ? "active" : ""}`}
      >
        ⚡ Bypass Mode (Direct URL)
      </button>
    </div>

    <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
      
      <div className="md:col-span-2 flex flex-col gap-6">

        {!hboDirectMode ? (
          <>
            {/* Login trigger card */}
            <div className="glass-panel p-8 rounded-xl border border-glass flex flex-col gap-6 glow-purple-card glow-card-premium">
              <h3 className="font-extrabold text-lg text-white">Prijava (Login)</h3>
              <p className="text-xs text-text-secondary leading-relaxed">
                HBO koristi autentifikaciju preko koda. Klikom na dugme pokrećete sesiju u pozadini koja će izgenerisati kod za prijavu. Detaljan kod i link ćete videti otvaranjem <strong>Logs</strong> dugmeta na kartici prijave u redu preuzimanja!
              </p>
              
              <div className="flex gap-4 items-end">
                <div className="flex-1">
                  <label>Region / Tržište (Market)</label>
                  <CustomSelect
                    value={hboMarket}
                    options={["emea", "us"]}
                    onChange={(val) => setHboMarket(val)}
                    formatLabel={(val) => val === "emea" ? "EMEA (Evropa - podrazumevano)" : "US (Amerika)"}
                  />
                </div>
                
                <button
                  onClick={startHboLogin}
                  className="btn btn-premium-secondary btn-align-select px-6"
                >
                  Pokreni Prijavu
                </button>
              </div>
            </div>

            {/* Standard Downloader Form */}
            <div className="glass-panel p-8 rounded-xl border border-glass flex flex-col gap-6 glow-purple-card glow-card-premium">
              <h3 className="font-extrabold text-lg text-white">Preuzimanje Videa (po ID-u)</h3>
              
              <div>
                <label>Video ID (Zadnji deo URL-a)</label>
                <div className="password-wrapper">
                  <Film className="absolute left-4 text-text-muted w-4 h-4" />
                  <input
                    type="text"
                    placeholder="npr. de4c9160-1b67-4c1e-8cad-e7b0e42c5fdf"
                    value={hboTarget}
                    onChange={(e) => setHboTarget(e.target.value)}
                    className="input-premium pl-11"
                    style={cssVars({"--focused-border": "#9333ea", "--focused-glow": "rgba(147,51,234,0.25)"})}
                  />
                </div>
                <p className="text-[10px] text-text-muted mt-1.5">
                  URL na HBO Max izgleda ovako: <code className="font-mono bg-white/[0.04] px-1 py-0.5 rounded text-indigo-400">.../watch/&lt;id1&gt;/&lt;id2&gt;</code>. Kopirajte samo <code className="font-mono text-indigo-400 font-bold">&lt;id2&gt;</code> (zadnji UUID).
                </p>
              </div>

              <div>
                <label>Jezici za titlove (odvojeni zarezom)</label>
                <div className="password-wrapper">
                  <Globe className="absolute left-4 text-text-muted w-4 h-4" />
                  <input
                    type="text"
                    placeholder="npr. sr,hr,mk,bs,sl ili 'none' za bez titlova"
                    value={hboSubs}
                    onChange={(e) => setHboSubs(e.target.value)}
                    className="input-premium pl-11"
                    style={cssVars({"--focused-border": "#9333ea", "--focused-glow": "rgba(147,51,234,0.25)"})}
                  />
                </div>
              </div>

              <button
                onClick={startHboDownload}
                disabled={!hboTarget}
                className="btn btn-premium-primary w-full py-4 text-white font-bold"
                style={cssVars({
                  "--btn-grad-start": "#9333ea",
                  "--btn-grad-end": "#7e22ce",
                  "--btn-glow": "rgba(147,51,234,0.25)",
                  "--btn-glow-hover": "rgba(147,51,234,0.45)"
                })}
              >
                <Download className="w-5 h-5" />
                Započni Preuzimanje
              </button>
            </div>
          </>
        ) : (
          /* ─── BYPASS / DIRECT MODE ─── */
          <div className="glass-panel p-8 rounded-xl border border-indigo-500/40 flex flex-col gap-6 glow-purple-card glow-card-premium" style={{background: "linear-gradient(135deg, rgba(99,102,241,0.08) 0%, rgba(139,92,246,0.06) 100%)"}}>
            <div className="flex items-center gap-3 mb-2">
              <span className="text-2xl">⚡</span>
              <div>
                <h3 className="font-extrabold text-lg text-white">Bypass Mode — Direktni URL-ovi</h3>
                <p className="text-xs text-indigo-300 mt-0.5">Zaobiđite login! Zalepite MPD Manifest i Widevine License URL iz DevTools-a ili browser-a.</p>
              </div>
            </div>

            <div className="p-4 rounded-lg bg-amber-500/10 border border-amber-500/30 text-xs text-amber-200 flex gap-2">
              <span className="text-base">💡</span>
              <div className="leading-relaxed">
                <strong>Kako do URL-ova?</strong> Otvorite DevTools (F12) → Network tab → pokrenite video na max.com → filtrirajte po <code className="font-mono bg-white/10 px-1 rounded">.mpd</code> za Manifest, i po <code className="font-mono bg-white/10 px-1 rounded">widevine</code> ili <code className="font-mono bg-white/10 px-1 rounded">license</code> za License URL.
              </div>
            </div>

            <div>
              <label>📄 Manifest URL (.mpd)</label>
              <div className="password-wrapper">
                <FileText className="absolute left-4 text-text-muted w-4 h-4" />
                <input
                  type="url"
                  placeholder="https://...cdn.max.com/.../.mpd?..."
                  value={hboManifestUrl}
                  onChange={(e) => setHboManifestUrl(e.target.value)}
                  className={`input-premium pl-11 ${hboManifestUrl && !hboManifestUrl.includes('mpd') ? 'border-amber-500/50' : ''}`}
                  style={cssVars({"--focused-border": "#9333ea", "--focused-glow": "rgba(147,51,234,0.25)"})}
                />
              </div>
              {hboManifestUrl && !hboManifestUrl.toLowerCase().includes('mpd') && (
                <p className="text-[10px] text-amber-400 mt-1">⚠ URL ne izgleda kao .mpd manifest – proverite URL</p>
              )}
            </div>

            <div>
              <label>🔑 License URL (Widevine)</label>
              <div className="password-wrapper">
                <Lock className="absolute left-4 text-text-muted w-4 h-4" />
                <input
                  type="url"
                  placeholder="https://widevine.any-any.prd.max.com/widevine/v1/license"
                  value={hboLicenseUrl}
                  onChange={(e) => setHboLicenseUrl(e.target.value)}
                  className="input-premium pl-11"
                  style={cssVars({"--focused-border": "#9333ea", "--focused-glow": "rgba(147,51,234,0.25)"})}
                />
              </div>
            </div>

            <div>
              <label>📝 Naslov (opciono)</label>
              <div className="password-wrapper">
                <Info className="absolute left-4 text-text-muted w-4 h-4" />
                <input
                  type="text"
                  placeholder="npr. Ime filma ili serije (ostavite prazno za auto)"
                  value={hboDirectTitle}
                  onChange={(e) => setHboDirectTitle(e.target.value)}
                  className="input-premium pl-11"
                  style={cssVars({"--focused-border": "#9333ea", "--focused-glow": "rgba(147,51,234,0.25)"})}
                />
              </div>
            </div>

            <div>
              <label>Jezici za titlove (odvojeni zarezom)</label>
              <div className="password-wrapper">
                <Globe className="absolute left-4 text-text-muted w-4 h-4" />
                <input
                  type="text"
                  placeholder="npr. sr,hr,mk,bs,sl ili 'none'"
                  value={hboDirectSubs}
                  onChange={(e) => setHboDirectSubs(e.target.value)}
                  className="input-premium pl-11"
                  style={cssVars({"--focused-border": "#9333ea", "--focused-glow": "rgba(147,51,234,0.25)"})}
                />
              </div>
            </div>

            <button
              onClick={startHboDirectDownload}
              disabled={!hboManifestUrl.trim() || !hboLicenseUrl.trim()}
              className="btn btn-premium-primary w-full py-4 text-white font-bold"
              style={cssVars({
                "--btn-grad-start": "#6366f1",
                "--btn-grad-end": "#8b5cf6",
                "--btn-glow": "rgba(99,102,241,0.25)",
                "--btn-glow-hover": "rgba(139,92,246,0.45)"
              })}
            >
              <Download className="w-5 h-5" />
              Pokreni Bypass Preuzimanje
            </button>
          </div>
        )}
      </div>

      {/* Account / status details */}
      <div className="flex flex-col gap-6">
        <div className="glass-panel p-6 rounded-xl border border-glass glow-purple-card glow-card-premium">
          <h3 className="font-extrabold text-base mb-4 flex items-center gap-2 text-white">
            <User className="w-5 h-5 text-purple-400" />
            Autentifikacija
          </h3>
          
          {status?.services.hbomax.authenticated ? (
            <div className="flex flex-col gap-3">
              <span className="badge flex items-center gap-1.5 bg-emerald-500/10 border-emerald-500/30 text-emerald-400 font-black px-2.5 py-1 text-[10px] tracking-wider rounded-md w-max" style={cssVars({animation: "pulseGlowBrighter 2s infinite", "--glow-color": "rgba(16, 185, 129, 0.2)"})}>
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 shadow-[0_0_8px_#34d399]"></span> PRIJAVLJEN PROFIL
              </span>
              <p className="text-xs text-text-secondary leading-relaxed">Token za prijavu je detektovan na sistemu. Preuzimanje će raditi automatski.</p>
            </div>
          ) : (
            <div className="flex flex-col gap-3">
              <span className="badge flex items-center gap-1.5 bg-red-500/10 border-red-500/30 text-red-400 font-black px-2.5 py-1 text-[10px] tracking-wider rounded-md w-max">
                <span className="w-1.5 h-1.5 rounded-full bg-red-400 animate-ping"></span> NEMA TOKENA
              </span>
              <p className="text-xs text-text-secondary leading-relaxed mt-1">Pokrenite proces prijave sa leve strane da biste kreirali HBO Max token.</p>
            </div>
          )}

          {/* Show active market */}
          <div className="mt-4 pt-4 border-t border-white/[0.04] flex items-center gap-2">
            <Globe className="w-4 h-4 text-text-muted" />
            <span className="text-xs text-text-secondary">Tržište (Market): <span className="font-bold text-white uppercase">{hboMarket}</span></span>
          </div>
        </div>

        {/* Direct mode info card */}
        {hboDirectMode && (
          <div className="glass-panel p-6 rounded-xl border border-glass flex flex-col gap-3 glow-purple-card glow-card-premium">
            <h3 className="font-extrabold text-base mb-3 flex items-center gap-2 text-white border-b border-white/[0.04] pb-3">
              <Zap className="w-5 h-5 text-purple-400 animate-pulse" />
              Bypass Mode Info
            </h3>
            <ul className="text-xs text-text-secondary flex flex-col gap-2.5">
              <li className="flex items-center gap-2">
                <Check className="w-4 h-4 text-emerald-400 flex-shrink-0" />
                <span><strong className="text-white">Ne treba login</strong> – rad sa sirovim URL-ovima</span>
              </li>
              <li className="flex items-center gap-2">
                <Check className="w-4 h-4 text-emerald-400 flex-shrink-0" />
                <span>Radi <strong className="text-white">bez sesije/tokena</strong> u fajlovima</span>
              </li>
              <li className="flex items-center gap-2">
                <ShieldAlert className="w-4 h-4 text-amber-400 flex-shrink-0" />
                <span>URL-ovi <strong className="text-amber-300">brzo isteknu</strong> – kopirajte i pokrenite odmah!</span>
              </li>
              <li className="flex items-center gap-2">
                <Check className="w-4 h-4 text-emerald-400 flex-shrink-0" />
                <span>Potreban je CDM (.wvd) za dekripciju</span>
              </li>
            </ul>
          </div>
        )}
      </div>
    </div>
  </div>
  );
}
