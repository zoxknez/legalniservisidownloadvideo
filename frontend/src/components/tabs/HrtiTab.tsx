import {
  AlertCircle,
  Check,
  Download,
  Film,
  List,
  Loader2,
  Lock,
  Search,
  ShieldAlert,
  Tv,
  User,
} from "lucide-react";
import { CustomSelect } from "../CustomSelect";
import type { HrtiItem } from "../../types/app";
import { useHrtiTab } from "../../hooks/domains/useHrtiTab";
import { cssVars } from "../../utils/cssVars";

export function HrtiTab() {
  const {
    catItems,
    catPage,
    catTotalPages,
    fetchHrtiCategoryItems,
    fetchHrtiSeriesEpisodes,
    hrtiCats,
    hrtiLoadingItems,
    hrtiSearchQuery,
    searchHrti,
    selectedCat,
    selectedHrtiSeries,
    setHrtiSearchQuery,
    setSelectedCat,
    startHrtiDownload,
    status,
  } = useHrtiTab();
  return (
<div key="hrti" className="tab-content tab-content-hrti">
    <div className="tab-page-header tab-header-hrti mb-8">
      <div className="tab-page-header-icon animate-pulse" style={{background:"linear-gradient(135deg,#06b6d4,#0284c7)"}}>
        <Film style={{width:24,height:24,color:"white"}} />
      </div>
      <div style={{flex:1}}>
        <div className="flex items-center justify-between flex-wrap gap-2">
          <h2 className="text-2xl font-extrabold text-white mb-1 flex items-center gap-2.5">
            <Film className="w-6 h-6 text-cyan-400" /> HRTi Catalog
          </h2>
          {status?.services.hrti.authenticated && (
            <span className="badge flex items-center gap-1.5 bg-cyan-500/10 border-cyan-500/30 text-cyan-400 font-black px-2.5 py-1 text-[10px] tracking-wider rounded-md">
              <Lock className="w-3.5 h-3.5" /> WIDEVINE L3 DEKRIPCIJA AKTIVNA
            </span>
          )}
        </div>
        <p className="text-text-secondary text-sm">Pregledajte, pretražujte i preuzmite filmove i serije sa HRTi streaming servisa uz automatsko dekodiranje.</p>
      </div>
    </div>

    <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
      {/* Left Column — Selector & Grid */}
      <div className="md:col-span-2 flex flex-col gap-6">
        
        {/* Category selector & Search bar */}
        <div className="glass-panel p-6 rounded-xl border border-glass flex flex-col md:flex-row gap-4 justify-between items-center glow-cyan-card glow-card-premium">
          <div className="flex items-center gap-3 w-full md:w-auto">
            <label className="m-0 text-xs text-text-secondary font-bold" style={{whiteSpace:"nowrap"}}>Kategorija:</label>
            <CustomSelect
              value={selectedCat}
              options={hrtiCats}
              onChange={(val) => {
                setSelectedCat(val);
                fetchHrtiCategoryItems(val, 1);
              }}
              formatLabel={(v) => v.replace(/_/g, " ").toUpperCase()}
              className="md-w-64"
            />
          </div>

          <div className="password-wrapper w-full md:w-96">
            <Search className="absolute left-4 text-text-muted w-4 h-4" />
            <input
              type="text"
              className="input-premium pl-11 pr-24"
              placeholder="Pretraži film ili seriju..."
              value={hrtiSearchQuery}
              onChange={(e) => setHrtiSearchQuery(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && searchHrti()}
              style={cssVars({"--focused-border": "#06b6d4", "--focused-glow": "rgba(6,182,212,0.25)"})}
            />
            <button
              onClick={searchHrti}
              className="btn btn-premium-primary absolute right-1.5 top-1.5 bottom-1.5 h-auto py-1 px-4 text-xs font-bold"
              style={cssVars({
                "--btn-grad-start": "#06b6d4",
                "--btn-grad-end": "#0891b2",
                "--btn-glow": "rgba(6,182,212,0.25)",
                "--btn-glow-hover": "rgba(6,182,212,0.45)",
                height: "calc(100% - 6px)",
                display: "flex",
                alignItems: "center"
              })}
            >
              Pretraži
            </button>
          </div>
        </div>

        {/* Items Grid */}
        <div className="glass-panel p-8 rounded-xl border border-glass min-h-96 relative glow-cyan-card glow-card-premium">
          {hrtiLoadingItems && (
            <div className="absolute inset-0 bg-black/40 flex items-center justify-center rounded-xl">
              <Loader2 className="w-12 h-12 text-cyan-500 animate-spin" />
            </div>
          )}

          {selectedHrtiSeries ? (
            <div className="flex justify-between items-center mb-6">
              <div className="flex items-center gap-2">
                <Film className="w-5 h-5 text-cyan-400" />
                <h3 className="font-extrabold text-xl text-white">Epizode za: {selectedHrtiSeries.title}</h3>
              </div>
              <button
                onClick={() => fetchHrtiCategoryItems(selectedCat, 1)}
                className="btn btn-secondary text-xs py-2 px-4"
              >
                Nazad na kategoriju
              </button>
            </div>
          ) : (
            <h3 className="font-extrabold text-xl mb-6 text-white">Sadržaj na HRTi</h3>
          )}

          {catItems.length === 0 ? (
            <div className="flex flex-col items-center justify-center p-20 text-center">
              <AlertCircle className="w-12 h-12 text-text-muted mb-4" />
              <p className="text-text-secondary font-semibold">Nema pronađenog sadržaja.</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {catItems.map((item: HrtiItem) => {
                const isMovie = item.type === "movie";
                const cardGlow = isMovie ? "rgba(6, 182, 212, 0.25)" : "rgba(147, 51, 234, 0.25)";
                return (
                  <div
                    key={item.id}
                    className="netflix-card group"
                    style={cssVars({ "--card-glow": cardGlow })}
                    onClick={() => {
                      if (item.type === "series") fetchHrtiSeriesEpisodes(item.id, item.title);
                      else startHrtiDownload(item.id, item.title);
                    }}
                  >
                    {/* Visual Thumbnail Gradient Backdrop */}
                    <div className={`absolute inset-0 w-full h-full flex items-center justify-center transition-transform duration-700 group-hover:scale-105 ${isMovie ? "hrti-thumbnail-movie" : "hrti-thumbnail-series"}`}>
                      {isMovie ? (
                        <Film className="w-16 h-16 opacity-10 text-indigo-300 transform -rotate-12 transition-transform duration-500 group-hover:scale-110 group-hover:rotate-0" />
                      ) : (
                        <Tv className="w-16 h-16 opacity-10 text-purple-300 transform rotate-12 transition-transform duration-500 group-hover:scale-110 group-hover:rotate-0" />
                      )}
                    </div>

                    {/* Floating Top-Right Badge */}
                    <div className="netflix-card-badge">
                      {isMovie ? (
                        <span className="badge flex items-center gap-1.5 bg-cyan-500/25 border-cyan-500/40 text-cyan-300 font-extrabold px-2.5 py-1 rounded-md text-[10px] tracking-wider">
                          <Film className="w-3.5 h-3.5" /> FILM
                        </span>
                      ) : (
                        <span className="badge flex items-center gap-1.5 bg-purple-500/25 border-purple-500/40 text-purple-300 font-extrabold px-2.5 py-1 rounded-md text-[10px] tracking-wider">
                          <Tv className="w-3.5 h-3.5" /> SERIJA
                        </span>
                      )}
                    </div>

                    {/* Center Action Play Circle */}
                    <div className="netflix-card-play">
                      {item.type === "series" ? (
                        <List className="w-5 h-5 text-indigo-900" />
                      ) : (
                        <Download className="w-5 h-5 text-cyan-900" />
                      )}
                    </div>

                    {/* Lower metadata card details */}
                    <div className="netflix-card-content">
                      <h4 className="font-extrabold text-white text-base leading-snug line-clamp-1 group-hover:text-indigo-200 transition-colors">{item.title}</h4>
                      <p className="text-[9px] text-text-muted font-mono mt-1 select-all">{item.id}</p>
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          {/* Pagination */}
          {!selectedHrtiSeries && catTotalPages > 1 && (
            <div className="flex justify-center items-center gap-4 mt-10">
              <button
                disabled={catPage <= 1}
                onClick={() => fetchHrtiCategoryItems(selectedCat, catPage - 1)}
                className="btn btn-secondary text-xs py-2"
              >
                Prethodna
              </button>
              <span className="text-sm font-bold text-text-secondary">Stranica {catPage} od {catTotalPages}</span>
              <button
                disabled={catPage >= catTotalPages}
                onClick={() => fetchHrtiCategoryItems(selectedCat, catPage + 1)}
                className="btn btn-secondary text-xs py-2"
              >
                Sledeća
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Right Column — Status & Details */}
      <div className="flex flex-col gap-6">
        <div className="glass-panel p-6 rounded-xl border border-glass glow-cyan-card glow-card-premium">
          <h3 className="font-extrabold text-base mb-4 flex items-center gap-2 text-white">
            <User className="w-5 h-5 text-cyan-400" />
            Status Naloga
          </h3>
          
          {status?.services.hrti.authenticated ? (
            <div className="flex flex-col gap-3">
              <span className="badge flex items-center gap-1.5 bg-emerald-500/10 border-emerald-500/30 text-emerald-400 font-black px-2.5 py-1 text-[10px] tracking-wider rounded-md w-max" style={cssVars({animation: "pulseGlowBrighter 2s infinite", "--glow-color": "rgba(16, 185, 129, 0.2)"})}>
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 shadow-[0_0_8px_#34d399]"></span> PRIJAVLJEN PROFIL
              </span>
              <div className="flex flex-col gap-1.5 border-t border-white/[0.03] pt-3">
                <p className="text-xs font-bold text-text-secondary">E-mail adresa:</p>
                <p className="text-sm font-semibold text-white truncate bg-black/20 p-2 rounded border border-white/[0.02]">{status.services.hrti.email}</p>
              </div>
            </div>
          ) : (
            <div className="flex flex-col gap-3">
              <span className="badge flex items-center gap-1.5 bg-red-500/10 border-red-500/30 text-red-400 font-black px-2.5 py-1 text-[10px] tracking-wider rounded-md w-max">
                <span className="w-1.5 h-1.5 rounded-full bg-red-400 animate-ping"></span> NIJE PRIJAVLJEN
              </span>
              <p className="text-xs text-text-secondary leading-relaxed mt-1">Prijavite se u <strong>"Postavkama"</strong> sa vašim HRTi parametrima da biste otključali Widevine preuzimanja.</p>
            </div>
          )}
        </div>

        <div className="glass-panel p-6 rounded-xl border border-glass flex flex-col gap-4 glow-cyan-card glow-card-premium">
          <h4 className="font-extrabold text-sm flex items-center gap-2 text-cyan-400 border-b border-white/[0.04] pb-3">
            <ShieldAlert className="w-4 h-4" />
            Widevine & Decryption Engine
          </h4>
          <p className="text-xs text-text-secondary leading-relaxed">
            HRTi katalog i strimovi koriste Widevine DRM L3 i AES-128 enkripciju. Aplikacija vrši automatsku dekripciju:
          </p>
          <ul className="text-xs text-text-secondary flex flex-col gap-2.5 border-t border-white/[0.03] pt-3">
            <li className="flex items-start gap-2">
              <Check className="w-4 h-4 text-emerald-400 flex-shrink-0 mt-0.5" />
              <span>Ekstrakcija HLS/DASH manifest metapodataka</span>
            </li>
            <li className="flex items-start gap-2">
              <Check className="w-4 h-4 text-emerald-400 flex-shrink-0 mt-0.5" />
              <span>Pronalaženje DRM ključeva za HRT1/2/3/4 i VOD</span>
            </li>
            <li className="flex items-start gap-2">
              <Check className="w-4 h-4 text-emerald-400 flex-shrink-0 mt-0.5" />
              <span>Brzo preuzimanje i spajanje sa demuksiranjem</span>
            </li>
          </ul>
        </div>
      </div>
    </div>
  </div>
  );
}
