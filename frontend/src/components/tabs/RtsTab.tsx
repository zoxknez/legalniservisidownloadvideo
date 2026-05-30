import {
  Download,
  Globe,
  Hash,
  Info,
  Loader2,
  Lock,
  Radio,
  ShieldAlert,
  User,
} from "lucide-react";
import { useRtsTab } from "../../hooks/domains/useRtsTab";
import { cssVars } from "../../utils/cssVars";

export function RtsTab() {
  const {
    fetchRtsVideoInfo,
    rtsEndEp,
    rtsInfoLoading,
    rtsStartEp,
    rtsSubmitting,
    rtsTarget,
    rtsVerbose,
    rtsVideoInfo,
    setRtsEndEp,
    setRtsStartEp,
    setRtsTarget,
    setRtsVerbose,
    startRtsDownload,
    status,
  } = useRtsTab();
  return (
<div key="rts" className="tab-content tab-content-rts">
    <div className="tab-page-header tab-header-rts mb-8">
      <div className="tab-page-header-icon animate-pulse" style={{background:"linear-gradient(135deg,#f43f5e,#e11d48)"}}>
        <Radio style={{width:24,height:24,color:"white"}} />
      </div>
      <div style={{flex:1}}>
        <div className="flex items-center justify-between flex-wrap gap-2">
          <h2 className="text-2xl font-extrabold text-white mb-1 flex items-center gap-2.5">
            <Radio className="w-6 h-6 text-rose-500" /> RTS Planeta
          </h2>
          {status?.services.rtsplaneta.authenticated && (
            <span className="badge flex items-center gap-1.5 bg-rose-500/10 border-rose-500/30 text-rose-400 font-black px-2.5 py-1 text-[10px] tracking-wider rounded-md">
              <Lock className="w-3.5 h-3.5" /> WIDEVINE L3 DEKRIPCIJA AKTIVNA
            </span>
          )}
        </div>
        <p className="text-text-secondary text-sm">Preuzmite filmove i epizode serija sa RTS Planeta platforme. Podržava Widevine L3 dekripciju.</p>
        <p className="text-xs text-text-muted mt-1.5">Primeri linkova: <code className="font-mono text-rose-400 bg-white/[0.04] px-1.5 py-0.5 rounded">rtsplaneta.rs/sr_lat/serial/...</code> ili <code className="font-mono text-rose-400 bg-white/[0.04] px-1.5 py-0.5 rounded">.../film/...</code></p>
      </div>
    </div>

    <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
      
      <div className="md:col-span-2 glass-panel p-8 rounded-xl border border-glass flex flex-col gap-6 glow-rose-card glow-card-premium">
        <div>
          <label>URL Sadržaja sa RTS Planete</label>
          <div className="password-wrapper">
            <Globe className="absolute left-4 text-text-muted w-4 h-4" />
            <input
              type="text"
              placeholder="npr. https://rtsplaneta.rs/sr_lat/serial/4276399/ranjeni-orao"
              value={rtsTarget}
              onChange={(e) => setRtsTarget(e.target.value)}
              onBlur={(e) => fetchRtsVideoInfo(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && startRtsDownload()}
              className="input-premium pl-11"
              style={cssVars({"--focused-border": "#f43f5e", "--focused-glow": "rgba(244,63,94,0.25)"})}
            />
          </div>
          {rtsInfoLoading && (
            <p className="text-[10px] text-text-muted mt-1.5 flex items-center gap-1.5">
              <Loader2 className="w-3 h-3 animate-spin" /> Učitavam metapodatke...
            </p>
          )}
          {rtsVideoInfo?.title && !rtsInfoLoading && (
            <div className="mt-3 p-3 rounded-lg bg-rose-500/10 border border-rose-500/20 flex gap-3 items-start">
              {rtsVideoInfo.thumbnail && (
                <img src={rtsVideoInfo.thumbnail} alt="" className="w-16 h-10 object-cover rounded border border-white/10" />
              )}
              <div className="min-w-0">
                <p className="text-sm font-bold text-white truncate">{rtsVideoInfo.title}</p>
                {rtsVideoInfo.description && (
                  <p className="text-[10px] text-text-muted line-clamp-2 mt-0.5">{rtsVideoInfo.description}</p>
                )}
              </div>
            </div>
          )}
          <p className="text-[10px] text-text-muted mt-1.5">Unesite link ka epizodi ili glavnoj seriji.</p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label>Početna Epizoda (opciono)</label>
            <div className="password-wrapper">
              <Hash className="absolute left-4 text-text-muted w-4 h-4" />
              <input
                type="number"
                placeholder="npr. 1"
                value={rtsStartEp}
                onChange={(e) => setRtsStartEp(e.target.value)}
                className="input-premium pl-11"
                style={cssVars({"--focused-border": "#f43f5e", "--focused-glow": "rgba(244,63,94,0.25)"})}
              />
            </div>
          </div>
          <div>
            <label>Krajnja Epizoda (opciono)</label>
            <div className="password-wrapper">
              <Hash className="absolute left-4 text-text-muted w-4 h-4" />
              <input
                type="number"
                placeholder="npr. 5"
                value={rtsEndEp}
                onChange={(e) => setRtsEndEp(e.target.value)}
                className="input-premium pl-11"
                style={cssVars({"--focused-border": "#f43f5e", "--focused-glow": "rgba(244,63,94,0.25)"})}
              />
            </div>
          </div>
        </div>

        <label className="flex items-center gap-3 p-3 rounded border border-glass cursor-pointer select-none">
          <input
            type="checkbox"
            className="w-4 h-4 cursor-pointer"
            checked={rtsVerbose}
            onChange={(e) => setRtsVerbose(e.target.checked)}
          />
          <span className="text-sm font-semibold text-white">Prikaži debug logove (Verbose)</span>
        </label>

        <button
          onClick={startRtsDownload}
          disabled={!rtsTarget.trim() || rtsSubmitting}
          className="btn btn-premium-primary w-full py-4 text-white font-bold"
          style={cssVars({
            "--btn-grad-start": "#f43f5e",
            "--btn-grad-end": "#e11d48",
            "--btn-glow": "rgba(244,63,94,0.25)",
            "--btn-glow-hover": "rgba(244,63,94,0.45)"
          })}
        >
          {rtsSubmitting ? (
            <><Loader2 className="w-5 h-5 animate-spin" /> Slanje...</>
          ) : (
            <><Download className="w-5 h-5" /> Započni Preuzimanje</>
          )}
        </button>
      </div>

      {/* Status details */}
      <div className="flex flex-col gap-6">
        <div className="glass-panel p-6 rounded-xl border border-glass glow-rose-card glow-card-premium">
          <h3 className="font-extrabold text-base mb-4 flex items-center gap-2 text-white">
            <User className="w-5 h-5 text-rose-400" />
            Kredencijali
          </h3>
          
          {status?.services.rtsplaneta.authenticated ? (
            <div className="flex flex-col gap-3">
              <span className="badge flex items-center gap-1.5 bg-emerald-500/10 border-emerald-500/30 text-emerald-400 font-black px-2.5 py-1 text-[10px] tracking-wider rounded-md w-max" style={cssVars({animation: "pulseGlowBrighter 2s infinite", "--glow-color": "rgba(16, 185, 129, 0.2)"})}>
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 shadow-[0_0_8px_#34d399]"></span> POVEZAN NALOG
              </span>
              <div className="flex flex-col gap-1.5 border-t border-white/[0.03] pt-3">
                <p className="text-xs font-bold text-text-secondary">E-mail adresa:</p>
                <p className="text-sm font-semibold text-white truncate bg-black/20 p-2 rounded border border-white/[0.02]">{status.services.rtsplaneta.email}</p>
              </div>
            </div>
          ) : (
            <div className="flex flex-col gap-3">
              <span className="badge flex items-center gap-1.5 bg-red-500/10 border-red-500/30 text-red-400 font-black px-2.5 py-1 text-[10px] tracking-wider rounded-md w-max">
                <span className="w-1.5 h-1.5 rounded-full bg-red-400 animate-ping"></span> NEDOSTAJU
              </span>
              <p className="text-xs text-text-secondary leading-relaxed mt-1">Sačuvajte vaše RTS kredencijale u <strong>"Postavkama"</strong> da biste otključali RTS preuzimanja.</p>
            </div>
          )}
        </div>

        {/* CDM alert */}
        <div className="glass-panel p-6 rounded-xl border border-glass flex flex-col gap-3 glow-rose-card glow-card-premium">
          <h4 className="font-extrabold text-sm flex items-center gap-2 text-rose-400 border-b border-white/[0.04] pb-3">
            <ShieldAlert className="w-4 h-4" />
            Widevine L3 Potreban
          </h4>
          <p className="text-xs text-text-secondary leading-relaxed">
            RTS Planeta koristi Widevine enkripciju. Proverite da li imate sačuvan <code className="font-mono text-rose-400 bg-white/[0.04] px-1.5 py-0.5 rounded">device.wvd</code> fajl u folderu binaries ili rootu aplikacije za automatsko dešifrovanje strimova.
          </p>
        </div>

        {/* RTS Tutorial Box */}
        <div className="glass-panel p-6 rounded-xl border border-glass flex flex-col gap-3 glow-rose-card glow-card-premium">
          <h4 className="font-extrabold text-sm flex items-center gap-2 text-rose-400 border-b border-white/[0.04] pb-3">
            <Info className="w-4 h-4" />
            Kako preuzeti sa RTS-a:
          </h4>
          <ul className="text-xs text-text-secondary flex flex-col gap-3">
            <li className="flex items-start gap-2.5">
              <span className="w-5 h-5 rounded-full bg-rose-500/15 border border-rose-500/30 text-rose-400 font-extrabold text-[10px] flex items-center justify-center flex-shrink-0 mt-0.5">1</span>
              <span>Prijavite se na sajt <a href="https://rtsplaneta.rs" target="_blank" rel="noreferrer" className="text-rose-400 hover:underline font-bold">rtsplaneta.rs</a>.</span>
            </li>
            <li className="flex items-start gap-2.5">
              <span className="w-5 h-5 rounded-full bg-rose-500/15 border border-rose-500/30 text-rose-400 font-extrabold text-[10px] flex items-center justify-center flex-shrink-0 mt-0.5">2</span>
              <span>Kopirajte URL adresu filma ili serije.</span>
            </li>
            <li className="flex items-start gap-2.5">
              <span className="w-5 h-5 rounded-full bg-rose-500/15 border border-rose-500/30 text-rose-400 font-extrabold text-[10px] flex items-center justify-center flex-shrink-0 mt-0.5">3</span>
              <span>Nalepite link u polje sa leve strane.</span>
            </li>
            <li className="flex items-start gap-2.5">
              <span className="w-5 h-5 rounded-full bg-rose-500/15 border border-rose-500/30 text-rose-400 font-extrabold text-[10px] flex items-center justify-center flex-shrink-0 mt-0.5">4</span>
              <span>Unesite raspon epizoda po potrebi.</span>
            </li>
            <li className="flex items-start gap-2.5">
              <span className="w-5 h-5 rounded-full bg-rose-500/15 border border-rose-500/30 text-rose-400 font-extrabold text-[10px] flex items-center justify-center flex-shrink-0 mt-0.5">5</span>
              <span>Kliknite "Započni Preuzimanje" za preuzimanje epizoda.</span>
            </li>
          </ul>
        </div>
      </div>
    </div>
  </div>
  );
}
