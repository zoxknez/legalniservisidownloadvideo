import {
  Check,
  Download,
  FileText,
  Film,
  Info,
  List,
  Loader2,
  Lock,
  Search,
  ShieldAlert,
  Tv,
  User,
  X,
} from "lucide-react";
import { CustomSelect } from "../CustomSelect";
import type { VoyoEpisode } from "../../types/app";
import { useVoyoTab } from "../../hooks/domains/useVoyoTab";
import { cssVars } from "../../utils/cssVars";

export function VoyoTab() {
  const {
    searchVoyoSeries,
    selectedVoyoEpisodes,
    setSelectedVoyoEpisodes,
    setVoyoEpisodesRange,
    setVoyoMode,
    setVoyoRes,
    setVoyoSeriesData,
    setVoyoTarget,
    startVoyoDownload,
    status,
    voyoEpisodesRange,
    voyoMode,
    voyoRes,
    voyoSearching,
    voyoSeriesData,
    voyoTarget,
  } = useVoyoTab();
  return (
<div key="voyo" className="tab-content tab-content-voyo">
    <div className="tab-page-header tab-header-voyo mb-8">
      <div className="tab-page-header-icon animate-pulse" style={{background:"linear-gradient(135deg,#f97316,#ea580c)"}}>
        <Tv style={{width:24,height:24,color:"white"}} />
      </div>
      <div style={{flex:1}}>
        <div className="flex items-center justify-between flex-wrap gap-2">
          <h2 className="text-2xl font-extrabold text-white mb-1 flex items-center gap-2.5">
            <Tv className="w-6 h-6 text-orange-500" /> Voyo RS
          </h2>
          <span className="badge flex items-center gap-1.5 bg-orange-500/10 border-orange-500/30 text-orange-400 font-black px-2.5 py-1 text-[10px] tracking-wider rounded-md">
            <Lock className="w-3.5 h-3.5" /> WIDEVINE L3 DEKRIPCIJA AKTIVNA
          </span>
        </div>
        <p className="text-text-secondary text-sm">Preuzmite filmove, epizode i cele serije sa Voyo.rs platforme uz Widevine dekripciju. Podržava automatsko preuzimanje titlova i spajanje.</p>
      </div>
    </div>

    <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
      
      {/* Downloader Form */}
      <div className="md:col-span-2 glass-panel p-8 rounded-xl border border-glass flex flex-col gap-6 glow-orange-card glow-card-premium">
        <div>
          <label>Izaberite tip preuzimanja</label>
          <div className="sliding-tabs-wrapper">
            <div
              className="sliding-tabs-slider"
              style={{
                width: "calc(50% - 4px)",
                transform: `translateX(${voyoMode === "video" ? "0%" : "100%"})`
              }}
            />
            <button
              type="button"
              onClick={() => { setVoyoMode("video"); setVoyoSeriesData(null); setVoyoEpisodesRange(""); }}
              className={`sliding-tabs-btn ${voyoMode === "video" ? "active" : ""}`}
            >
              <Film className="w-4 h-4" /> Film / Epizoda
            </button>
            {/* Bug 7 Fix: also reset voyoEpisodesRange when switching to series */}
            <button
              type="button"
              onClick={() => { setVoyoMode("series"); setVoyoEpisodesRange(""); }}
              className={`sliding-tabs-btn ${voyoMode === "series" ? "active" : ""}`}
            >
              <List className="w-4 h-4" /> Cela Serija
            </button>
          </div>
        </div>

        <div>
          <label>{voyoMode === "video" ? "URL ili ID videa" : "ID serije"}</label>
          <div className="password-wrapper">
            {voyoMode === "video" ? (
              <Film className="absolute left-4 text-text-muted w-4 h-4" />
            ) : (
              <List className="absolute left-4 text-text-muted w-4 h-4" />
            )}
            <input
              type="text"
              placeholder={voyoMode === "video" ? "npr. https://voyo.rs/uspeh-1_50584.html ili ID 50584" : "npr. 542"}
              value={voyoTarget}
              onChange={(e) => setVoyoTarget(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && voyoMode === "series" && searchVoyoSeries()}
              className="input-premium pl-11 pr-24"
              style={cssVars({"--focused-border": "#f97316", "--focused-glow": "rgba(249,115,22,0.25)"})}
            />
            {voyoMode === "series" && (
              <button
                type="button"
                onClick={searchVoyoSeries}
                disabled={voyoSearching || !voyoTarget}
                className="btn btn-premium-primary absolute right-1.5 top-1.5 bottom-1.5 h-auto py-1 px-4 text-xs font-bold"
                style={cssVars({
                  "--btn-grad-start": "#f97316",
                  "--btn-grad-end": "#ea580c",
                  "--btn-glow": "rgba(249,115,22,0.25)",
                  "--btn-glow-hover": "rgba(249,115,22,0.45)",
                  height: "calc(100% - 6px)",
                  display: "flex",
                  alignItems: "center"
                })}
              >
                {voyoSearching ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Search className="w-3.5 h-3.5" />}
                Pretraži
              </button>
            )}
          </div>
        </div>

        <div>
          <label>Kvalitet preuzimanja (Resolution)</label>
          <CustomSelect
            value={voyoRes}
            options={["1080p", "720p", "480p"]}
            onChange={(val) => setVoyoRes(val)}
            formatLabel={(val) => val === "1080p" ? "1080p (Full HD - podrazumevano)" : val === "720p" ? "720p (HD)" : "480p (SD)"}
          />
        </div>

        {/* Series Details & Episode Checklist */}
        {voyoMode === "series" && voyoSeriesData && (
          <div className="border-t border-glass pt-6 flex flex-col gap-4">
            <div>
              <h3 className="font-extrabold text-lg text-orange-500">{voyoSeriesData.title}</h3>
              <p className="text-xs text-text-secondary mt-1">{voyoSeriesData.description}</p>
            </div>

            <div>
              <div className="flex justify-between items-center mb-2">
                <label className="m-0 font-bold text-xs">Epizode u seriji ({voyoSeriesData.episodes.length})</label>
                <div className="flex gap-2">
                  <button
                    type="button"
                    className="text-[10px] uppercase font-extrabold text-orange-400 bg-orange-500/5 hover:bg-orange-500/15 border border-orange-500/10 hover:border-orange-500/20 px-2 py-1 rounded transition-all flex items-center gap-1"
                    onClick={() => setSelectedVoyoEpisodes(voyoSeriesData.episodes.map((e: VoyoEpisode) => e.id))}
                  >
                    <Check className="w-3 h-3" /> Označi sve
                  </button>
                  <button
                    type="button"
                    className="text-[10px] uppercase font-extrabold text-text-muted bg-white/[0.02] border border-white/[0.05] hover:bg-white/[0.05] px-2 py-1 rounded transition-all flex items-center gap-1"
                    onClick={() => setSelectedVoyoEpisodes([])}
                  >
                    <X className="w-3 h-3" /> Odznači sve
                  </button>
                </div>
              </div>

              <div className="max-h-60 overflow-y-auto border border-glass rounded-lg bg-black/40 p-2 flex flex-col gap-1">
                {voyoSeriesData.episodes.map((ep: VoyoEpisode) => {
                  const checked = selectedVoyoEpisodes.includes(ep.id);
                  return (
                    <div key={ep.id} className="custom-checkbox-wrap" style={cssVars({borderRadius:8,padding:"8px 10px", "--checkbox-bg": "#ea580c", "--checkbox-glow": "rgba(249, 115, 22, 0.3)"})} onClick={() => {
                      if (checked) setSelectedVoyoEpisodes(selectedVoyoEpisodes.filter((id: number) => id !== ep.id));
                      else setSelectedVoyoEpisodes([...selectedVoyoEpisodes, ep.id]);
                    }}>
                      <div className={`custom-checkbox-box ${checked ? "checked" : ""}`}>
                        <svg className="custom-checkbox-check" viewBox="0 0 10 10" fill="none" stroke="white" strokeWidth="2">
                          <polyline points="1.5 5 4 7.5 8.5 2" />
                        </svg>
                      </div>
                      <span className="font-extrabold text-[10px] tracking-wider uppercase bg-orange-500/10 text-orange-400 border border-orange-500/20 px-2 py-0.5 rounded min-w-16 text-center">S{ep.season.toString().padStart(2, "0")}E{ep.episode.toString().padStart(2, "0")}</span>
                      <span className="flex-1 truncate text-white text-sm font-semibold">{ep.title}</span>
                      <span className="text-xs text-text-muted">{ep.length_mins}m</span>
                      {ep.drm && <span title="DRM Zaštićeno"><Lock className="w-3.5 h-3.5 text-amber-500" /></span>}
                      {ep.has_subs && <span title="Titlovi dostupni"><FileText className="w-3.5 h-3.5 text-indigo-400" /></span>}
                    </div>
                  );
                })}
              </div>
            </div>

            {/* F4: Clarify range vs checkbox priority */}
            <div className="border-t border-white/[0.03] pt-4">
              <label>Raspon epizoda (opciono)</label>
              <input
                type="text"
                placeholder="npr. 1-3, 5-, -4"
                value={voyoEpisodesRange}
                onChange={(e) => setVoyoEpisodesRange(e.target.value)}
                className="input-premium"
                style={cssVars({"--focused-border": "#f97316", "--focused-glow": "rgba(249,115,22,0.25)"})}
              />
              <p className="text-[11px] text-amber-400 mt-1.5 flex items-center gap-1">
                <Info className="w-3 h-3 flex-shrink-0" />
                {voyoEpisodesRange
                  ? "⚡ Raspon ima prioritet — checkbox selekcija se ignoriše kada je raspon unesen."
                  : "Ostavi prazno da koristiš epizode označene checkboxom gore."}
              </p>
            </div>
          </div>
        )}

        <button
          onClick={startVoyoDownload}
          disabled={!voyoTarget}
          className="btn-premium btn-premium-primary w-full py-4 text-base font-extrabold"
          style={cssVars({
            "--btn-grad-start": "#f97316",
            "--btn-grad-end": "#ea580c",
            "--btn-glow": "rgba(249,115,22,0.3)",
            "--btn-glow-hover": "rgba(249,115,22,0.45)"
          })}
        >
          <Download className="w-5 h-5" />
          Započni Preuzimanje
        </button>
      </div>

      {/* Account / Service details */}
      <div className="flex flex-col gap-6">
        <div className="glass-panel p-6 rounded-xl border border-glass glow-orange-card glow-card-premium">
          <h3 className="font-extrabold text-base mb-4 flex items-center gap-2 text-white">
            <User className="w-5 h-5 text-orange-400" />
            Status Naloga
          </h3>
          
          {status?.services.voyo.authenticated ? (
            <div className="flex flex-col gap-3">
              <span className="badge flex items-center gap-1.5 bg-emerald-500/10 border-emerald-500/30 text-emerald-400 font-black px-2.5 py-1 text-[10px] tracking-wider rounded-md w-max" style={cssVars({animation: "pulseGlowBrighter 2s infinite", "--glow-color": "rgba(16, 185, 129, 0.2)"})}>
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 shadow-[0_0_8px_#34d399]"></span> PRIJAVLJEN PROFIL
              </span>
              <div className="flex flex-col gap-1.5 border-t border-white/[0.03] pt-3">
                <p className="text-xs font-bold text-text-secondary">E-mail adresa:</p>
                <p className="text-sm font-semibold text-white truncate bg-black/20 p-2 rounded border border-white/[0.02]">{status.services.voyo.email}</p>
              </div>
              <div className="flex justify-between items-center text-xs font-semibold text-white bg-black/10 p-2 rounded">
                <span className="text-text-secondary">Aktivna pretplata:</span>
                <span className={status.services.voyo.subscribed ? "text-emerald-400 font-black" : "text-red-400 font-black"}>
                  {status.services.voyo.subscribed ? "AKTIVNA ✓" : "NEAKTIVNA ✗"}
                </span>
              </div>
            </div>
          ) : (
            <div className="flex flex-col gap-3">
              <span className="badge flex items-center gap-1.5 bg-red-500/10 border-red-500/30 text-red-400 font-black px-2.5 py-1 text-[10px] tracking-wider rounded-md w-max">
                <span className="w-1.5 h-1.5 rounded-full bg-red-400 animate-ping"></span> NIJE PRIJAVLJEN
              </span>
              <p className="text-xs text-text-secondary leading-relaxed mt-1">Prijavite se u <strong>"Postavkama"</strong> sa vašim Voyo.rs parametrima da biste otključali Widevine preuzimanja.</p>
            </div>
          )}
        </div>

        {/* Voyo Tech / DRM info box */}
        <div className="glass-panel p-6 rounded-xl border border-glass flex flex-col gap-4 glow-orange-card glow-card-premium">
          <h4 className="font-extrabold text-sm flex items-center gap-2 text-orange-400 border-b border-white/[0.04] pb-3">
            <ShieldAlert className="w-4 h-4" />
            Widevine & DRM Engine
          </h4>
          <p className="text-xs text-text-secondary leading-relaxed">
            Voyo.rs koristi AES-128 enkripciju i Widevine DRM L3 za zaštitu sadržaja. Naš preuzimač integriše napredne dekripcione module:
          </p>
          <ul className="text-xs text-text-secondary flex flex-col gap-2.5 border-t border-white/[0.03] pt-3">
            <li className="flex items-start gap-2">
              <Check className="w-4 h-4 text-emerald-400 flex-shrink-0 mt-0.5" />
              <span>Widevine DRM L3 automatsko preuzimanje ključeva</span>
            </li>
            <li className="flex items-start gap-2">
              <Check className="w-4 h-4 text-emerald-400 flex-shrink-0 mt-0.5" />
              <span>Automatska ekstrakcija i spajanje SR/HR titlova</span>
            </li>
            <li className="flex items-start gap-2">
              <Check className="w-4 h-4 text-emerald-400 flex-shrink-0 mt-0.5" />
              <span>Remuxing audio/video tokova u finalni MKV format</span>
            </li>
          </ul>
        </div>
      </div>
    </div>
  </div>
  );
}
