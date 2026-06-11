import {
  Check,
  Clapperboard,
  Clipboard,
  Download,
  FileText,
  Film,
  Globe,
  HardDrive,
  Info,
  KeyRound,
  Lock,
  RefreshCw,
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
    hboDirectAudio,
    hboDirectTitle,
    hboLicenseUrl,
    hboManifestUrl,
    hboMarket,
    hboSubs,
    hboAudio,
    hboTarget,
    hboSubmitting,
    hboAuth,
    refreshAuth,
    pasteHboTarget,
    setHboDirectMode,
    setHboDirectSubs,
    setHboDirectAudio,
    setHboDirectTitle,
    setHboLicenseUrl,
    setHboManifestUrl,
    setHboMarket,
    setHboSubs,
    setHboAudio,
    setHboTarget,
    startHboDirectDownload,
    startHboDownload,
    startHboLogin,
    status,
  } = useHboTab();

  const isAuthenticated = hboAuth?.authenticated ?? status?.services?.hbomax?.authenticated ?? false;

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
        <p className="text-text-secondary text-sm">Prijava uređaja, preuzimanje po URL-u ili Video ID-u, ili Bypass Mode sa direktnim MPD/License URL-ovima.</p>
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
        Bypass Mode (Direct URL)
      </button>
    </div>

    <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
      
      <div className="md:col-span-2 flex flex-col gap-6">

        {!hboDirectMode ? (
          <>
            {/* Login trigger card */}
            <div className="glass-panel p-8 rounded-xl border border-glass flex flex-col gap-6 glow-purple-card glow-card-premium">
              <h3 className="font-extrabold text-lg text-white flex items-center gap-2">
                <KeyRound className="w-5 h-5 text-purple-400" />
                Prijava (Login)
              </h3>
              <p className="text-xs text-text-secondary leading-relaxed">
                HBO koristi autentifikaciju preko koda. Klikom na dugme pokrećete sesiju u pozadini koja će izgenerisati kod za prijavu. Detaljan kod i link ćete videti otvaranjem <strong className="text-white">Logs</strong> dugmeta na kartici prijave u redu preuzimanja.
              </p>
              
              <div className="flex gap-4 items-end">
                <div className="flex-1">
                  <label>Region / Tržište (Market)</label>
                  <CustomSelect
                    value={hboMarket}
                    options={["emea", "latam", "us"]}
                    onChange={(val) => setHboMarket(val)}
                    formatLabel={(val) =>
                      val === "emea" ? "EMEA (Evropa - podrazumevano)" :
                      val === "latam" ? "LATAM (Latinska Amerika)" :
                      "US (Amerika)"
                    }
                  />
                </div>
                
                <button
                  onClick={startHboLogin}
                  disabled={hboSubmitting}
                  className="btn btn-premium-secondary btn-align-select px-6"
                >
                  {hboSubmitting ? "Pokretanje..." : "Pokreni Prijavu"}
                </button>
              </div>
            </div>

            {/* Standard Downloader Form */}
            <div className="glass-panel p-8 rounded-xl border border-glass flex flex-col gap-6 glow-purple-card glow-card-premium">
              <h3 className="font-extrabold text-lg text-white flex items-center gap-2">
                <Film className="w-5 h-5 text-purple-400" />
                Preuzimanje Videa
              </h3>
              
              <div>
                <label>Video URL ili ID</label>
                <div className="password-wrapper">
                  <Film className="absolute left-4 text-text-muted w-4 h-4" />
                  <input
                    type="text"
                    placeholder="Zalepite pun URL ili samo UUID — npr. de4c9160-1b67-4c1e-8cad-..."
                    value={hboTarget}
                    onChange={(e) => setHboTarget(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && !hboSubmitting && hboTarget.trim() && startHboDownload()}
                    className="input-premium pl-11 pr-11"
                    style={cssVars({"--focused-border": "#9333ea", "--focused-glow": "rgba(147,51,234,0.25)"})}
                  />
                  <button
                    type="button"
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-text-muted hover:text-purple-400 transition-colors p-1 rounded"
                    title="Nalepi iz clipboard-a"
                    onClick={pasteHboTarget}
                  >
                    <Clipboard className="w-4 h-4" />
                  </button>
                </div>
                <p className="text-[10px] text-text-muted mt-1.5">
                  Zalepite kompletan link sa max.com/hbomax.com ili samo zadnji UUID iz URL-a. Sistem automatski prepoznaje ID.
                </p>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label>Titlovi</label>
                  <div className="password-wrapper">
                    <Globe className="absolute left-4 text-text-muted w-4 h-4" />
                    <input
                      type="text"
                      placeholder="all, sr,hr,en ili none"
                      value={hboSubs}
                      onChange={(e) => setHboSubs(e.target.value)}
                      onKeyDown={(e) => e.key === "Enter" && !hboSubmitting && hboTarget.trim() && startHboDownload()}
                      className="input-premium pl-11"
                      style={cssVars({"--focused-border": "#9333ea", "--focused-glow": "rgba(147,51,234,0.25)"})}
                    />
                  </div>
                  <p className="text-[10px] text-text-muted mt-1">Podrazumevano <code className="font-mono">all</code> — svi titlovi iz manifesta.</p>
                </div>
                <div>
                  <label>Audio trake</label>
                  <CustomSelect
                    value={hboAudio}
                    options={["all", "first"]}
                    onChange={(val) => setHboAudio(val)}
                    formatLabel={(val) =>
                      val === "all" ? "Svi jezici (preporučeno)" : "Samo primarni (en/und)"
                    }
                  />
                </div>
              </div>

              <button
                onClick={startHboDownload}
                disabled={!hboTarget.trim() || hboSubmitting}
                className="btn btn-premium-primary w-full py-4 text-white font-bold"
                style={cssVars({
                  "--btn-grad-start": "#9333ea",
                  "--btn-grad-end": "#7e22ce",
                  "--btn-glow": "rgba(147,51,234,0.25)",
                  "--btn-glow-hover": "rgba(147,51,234,0.45)"
                })}
              >
                <Download className="w-5 h-5" />
                {hboSubmitting ? "Slanje..." : "Započni Preuzimanje"}
              </button>
            </div>
          </>
        ) : (
          /* BYPASS / DIRECT MODE */
          <div className="glass-panel p-8 rounded-xl border border-indigo-500/40 flex flex-col gap-6 glow-purple-card glow-card-premium" style={{background: "linear-gradient(135deg, rgba(99,102,241,0.08) 0%, rgba(139,92,246,0.06) 100%)"}}>
            <div className="flex items-center gap-3 mb-2">
              <div className="w-10 h-10 rounded-lg bg-indigo-500/20 flex items-center justify-center flex-shrink-0">
                <Zap className="w-5 h-5 text-indigo-400" />
              </div>
              <div>
                <h3 className="font-extrabold text-lg text-white">Bypass Mode — Direktni URL-ovi</h3>
                <p className="text-xs text-indigo-300 mt-0.5">Zalepite MPD Manifest i Widevine License URL iz DevTools-a.</p>
              </div>
            </div>

            <div className="p-4 rounded-lg bg-amber-500/10 border border-amber-500/30 text-xs text-amber-200 flex gap-2">
              <ShieldAlert className="w-4 h-4 text-amber-400 flex-shrink-0 mt-0.5" />
              <div className="leading-relaxed">
                <strong>Kako do URL-ova?</strong> Otvorite DevTools (F12) → Network tab → pokrenite video na max.com → filtrirajte po <code className="font-mono bg-white/10 px-1 rounded">.mpd</code> za Manifest, i po <code className="font-mono bg-white/10 px-1 rounded">widevine</code> ili <code className="font-mono bg-white/10 px-1 rounded">license</code> za License URL.
              </div>
            </div>

            <div>
              <label>Manifest URL (.mpd)</label>
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
                <p className="text-[10px] text-amber-400 mt-1 flex items-center gap-1">
                  <ShieldAlert className="w-3 h-3" /> URL ne izgleda kao .mpd manifest – proverite
                </p>
              )}
            </div>

            <div>
              <label>License URL (Widevine)</label>
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
              <label>Naslov (opciono)</label>
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

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label>Titlovi</label>
                <div className="password-wrapper">
                  <Globe className="absolute left-4 text-text-muted w-4 h-4" />
                  <input
                    type="text"
                    placeholder="all, sr,hr,en ili none"
                    value={hboDirectSubs}
                    onChange={(e) => setHboDirectSubs(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && !hboSubmitting && hboManifestUrl.trim() && hboLicenseUrl.trim() && startHboDirectDownload()}
                    className="input-premium pl-11"
                    style={cssVars({"--focused-border": "#9333ea", "--focused-glow": "rgba(147,51,234,0.25)"})}
                  />
                </div>
              </div>
              <div>
                <label>Audio trake</label>
                <CustomSelect
                  value={hboDirectAudio}
                  options={["all", "first"]}
                  onChange={(val) => setHboDirectAudio(val)}
                  formatLabel={(val) =>
                    val === "all" ? "Svi jezici (preporučeno)" : "Samo primarni (en/und)"
                  }
                />
              </div>
            </div>

            <button
              onClick={startHboDirectDownload}
              disabled={!hboManifestUrl.trim() || !hboLicenseUrl.trim() || hboSubmitting}
              className="btn btn-premium-primary w-full py-4 text-white font-bold"
              style={cssVars({
                "--btn-grad-start": "#6366f1",
                "--btn-grad-end": "#8b5cf6",
                "--btn-glow": "rgba(99,102,241,0.25)",
                "--btn-glow-hover": "rgba(139,92,246,0.45)"
              })}
            >
              <Download className="w-5 h-5" />
              {hboSubmitting ? "Slanje..." : "Pokreni Bypass Preuzimanje"}
            </button>
          </div>
        )}
      </div>

      {/* Sidebar */}
      <div className="flex flex-col gap-6">

        {/* Auth status card */}
        <div className="glass-panel p-6 rounded-xl border border-glass glow-purple-card glow-card-premium">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-extrabold text-base flex items-center gap-2 text-white">
              <User className="w-5 h-5 text-purple-400" />
              Autentifikacija
            </h3>
            <button
              type="button"
              className="text-text-muted hover:text-purple-400 transition-colors p-1 rounded"
              title="Osveži status"
              onClick={refreshAuth}
            >
              <RefreshCw className="w-3.5 h-3.5" />
            </button>
          </div>
          
          {isAuthenticated ? (
            <div className="flex flex-col gap-3">
              <span className="badge flex items-center gap-1.5 bg-emerald-500/10 border-emerald-500/30 text-emerald-400 font-black px-2.5 py-1 text-[10px] tracking-wider rounded-md w-max" style={cssVars({animation: "pulseGlowBrighter 2s infinite", "--glow-color": "rgba(16, 185, 129, 0.2)"})}>
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 shadow-[0_0_8px_#34d399]"></span> PRIJAVLJEN
              </span>
              <p className="text-xs text-text-secondary leading-relaxed">Token za prijavu je aktivan. Preuzimanje će raditi automatski.</p>
              {hboAuth?.token_path && (
                <p className="text-[10px] text-text-muted break-all mt-1 font-mono bg-white/[0.03] px-2 py-1.5 rounded">
                  {hboAuth.token_path}
                </p>
              )}
            </div>
          ) : (
            <div className="flex flex-col gap-3">
              <span className="badge flex items-center gap-1.5 bg-red-500/10 border-red-500/30 text-red-400 font-black px-2.5 py-1 text-[10px] tracking-wider rounded-md w-max">
                <span className="w-1.5 h-1.5 rounded-full bg-red-400 animate-ping"></span> NEMA TOKENA
              </span>
              <p className="text-xs text-text-secondary leading-relaxed mt-1">
                {hboDirectMode
                  ? "Bypass mode radi bez tokena — zalepite MPD i License URL."
                  : "Pokrenite proces prijave da biste kreirali HBO Max token."}
              </p>
            </div>
          )}

          {/* Active market */}
          <div className="mt-4 pt-4 border-t border-white/[0.04] flex items-center gap-2">
            <Globe className="w-4 h-4 text-text-muted" />
            <span className="text-xs text-text-secondary">Tržište: <span className="font-bold text-white uppercase">{hboMarket}</span></span>
          </div>
        </div>

        {/* CDM Status */}
        <div className="glass-panel p-6 rounded-xl border border-glass glow-purple-card glow-card-premium">
          <h3 className="font-extrabold text-base mb-3 flex items-center gap-2 text-white">
            <HardDrive className="w-5 h-5 text-purple-400" />
            CDM Uređaj
          </h3>
          {status?.binaries?.device_wvd?.found ? (
            <div className="flex flex-col gap-2">
              <span className="badge flex items-center gap-1.5 bg-emerald-500/10 border-emerald-500/30 text-emerald-400 font-black px-2 py-1 text-[10px] tracking-wider rounded-md w-max">
                <Check className="w-3 h-3" /> CDM SPREMAN
              </span>
              <p className="text-[10px] text-text-muted break-all font-mono bg-white/[0.03] px-2 py-1.5 rounded mt-1">
                {status.binaries.device_wvd.path}
              </p>
            </div>
          ) : (
            <div className="flex flex-col gap-2">
              <span className="badge flex items-center gap-1.5 bg-amber-500/10 border-amber-500/30 text-amber-400 font-black px-2 py-1 text-[10px] tracking-wider rounded-md w-max">
                <ShieldAlert className="w-3 h-3" /> CDM NIJE PRONAĐEN
              </span>
              <p className="text-xs text-text-secondary leading-relaxed mt-1">
                Potreban je <code className="font-mono bg-white/[0.04] px-1 rounded text-purple-300">.wvd</code> fajl za Widevine dekripciju. Postavite ga u root projekta ili u <code className="font-mono bg-white/[0.04] px-1 rounded text-purple-300">~/.wvd/</code> folder.
              </p>
            </div>
          )}
        </div>

        {/* Mode-specific info cards */}
        {hboDirectMode ? (
          <div className="glass-panel p-6 rounded-xl border border-glass flex flex-col gap-3 glow-purple-card glow-card-premium">
            <h3 className="font-extrabold text-base mb-3 flex items-center gap-2 text-white border-b border-white/[0.04] pb-3">
              <Zap className="w-5 h-5 text-indigo-400" />
              Bypass Mode Info
            </h3>
            <ul className="text-xs text-text-secondary flex flex-col gap-2.5">
              <li className="flex items-center gap-2">
                <Check className="w-4 h-4 text-emerald-400 flex-shrink-0" />
                <span><strong className="text-white">Direktni MPD/License URL-ovi</strong> — zaobilazi HBO API pretragu</span>
              </li>
              <li className="flex items-center gap-2">
                <ShieldAlert className="w-4 h-4 text-amber-400 flex-shrink-0" />
                <span>URL-ovi <strong className="text-amber-300">brzo isteknu</strong> – kopirajte i pokrenite odmah</span>
              </li>
              <li className="flex items-center gap-2">
                <Check className="w-4 h-4 text-emerald-400 flex-shrink-0" />
                <span>Potreban je CDM (.wvd) za dekripciju</span>
              </li>
            </ul>
          </div>
        ) : (
          <div className="glass-panel p-6 rounded-xl border border-glass flex flex-col gap-3 glow-purple-card glow-card-premium">
            <h3 className="font-extrabold text-base mb-3 flex items-center gap-2 text-white border-b border-white/[0.04] pb-3">
              <Info className="w-5 h-5 text-purple-400" />
              Brzi Vodič
            </h3>
            <ol className="text-xs text-text-secondary flex flex-col gap-2.5 list-none">
              <li className="flex gap-2">
                <span className="w-5 h-5 rounded-full bg-purple-500/20 text-purple-300 flex items-center justify-center flex-shrink-0 text-[10px] font-bold">1</span>
                <span>Pokrenite <strong className="text-white">Prijavu</strong> i unesite kod na ekranu</span>
              </li>
              <li className="flex gap-2">
                <span className="w-5 h-5 rounded-full bg-purple-500/20 text-purple-300 flex items-center justify-center flex-shrink-0 text-[10px] font-bold">2</span>
                <span>Kopirajte <strong className="text-white">pun link</strong> sa max.com ili samo UUID</span>
              </li>
              <li className="flex gap-2">
                <span className="w-5 h-5 rounded-full bg-purple-500/20 text-purple-300 flex items-center justify-center flex-shrink-0 text-[10px] font-bold">3</span>
                <span>Zalepite u polje i kliknite <strong className="text-white">Preuzimanje</strong></span>
              </li>
            </ol>
          </div>
        )}
      </div>
    </div>
  </div>
  );
}
