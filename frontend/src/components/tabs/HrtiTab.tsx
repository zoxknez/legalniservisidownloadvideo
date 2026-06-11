import {
  AlertCircle,
  Download,
  Film,
  Link2,
  List,
  Loader2,
  Lock,
  Search,
  Tv,
} from "lucide-react";
import { CustomSelect } from "../CustomSelect";
import { HrtiSeasonList } from "../hrti/HrtiSeasonList";
import { HrtiSidebar } from "../hrti/HrtiSidebar";
import type { HrtiItem } from "../../types/app";
import { useHrtiTab } from "../../hooks/domains/useHrtiTab";
import { cssVars } from "../../utils/cssVars";

function pluralEpizoda(n: number): string {
  if (n === 1) return "epizodu";
  if (n >= 2 && n <= 4) return "epizode";
  return "epizoda";
}

export function HrtiTab() {
  const {
    backToCatalog,
    catItems,
    catPage,
    catTotalPages,
    confirmHrtiBatchDownload,
    fetchHrtiCategoryItems,
    fetchHrtiSeriesEpisodes,
    hrtiCats,
    hrtiLoadError,
    hrtiLoadingItems,
    hrtiSearchQuery,
    hrtiSeriesSeasons,
    hrtiSubmitting,
    hrtiUrlInput,
    hrtiWorkers,
    resolveHrtiUrl,
    searchHrti,
    selectedCat,
    selectedHrtiEpisodes,
    selectedHrtiSeries,
    setHrtiSearchQuery,
    setHrtiUrlInput,
    setHrtiWorkers,
    setSelectedCat,
    setSelectedHrtiEpisodes,
    startHrtiDownload,
    status,
    viewMode,
  } = useHrtiTab();

  const authenticated = status?.services?.hrti?.authenticated ?? false;
  const cdmReady = status?.drm?.cdm_ready ?? status?.binaries?.device_wvd?.found ?? false;
  const canDownload = authenticated && cdmReady;

  const categoryOptions = hrtiCats.map((c) => c.id);
  const formatCategory = (id: string) => {
    const cat = hrtiCats.find((c) => c.id === id);
    return cat?.name || id.replace(/_/g, " ");
  };

  const batchLabel =
    selectedHrtiEpisodes.length > 0
      ? `Preuzmi ${selectedHrtiEpisodes.length} ${pluralEpizoda(selectedHrtiEpisodes.length)}`
      : "Izaberite epizode";

  return (
    <div key="hrti" className="tab-content tab-content-hrti">
      <div className="tab-page-header tab-header-hrti mb-8">
        <div
          className="tab-page-header-icon"
          style={{ background: "linear-gradient(135deg,#06b6d4,#0284c7)" }}
        >
          <Film style={{ width: 24, height: 24, color: "white" }} />
        </div>
        <div style={{ flex: 1 }}>
          <div className="flex items-center justify-between flex-wrap gap-2">
            <h2 className="text-2xl font-extrabold text-white mb-1 flex items-center gap-2.5">
              <Film className="w-6 h-6 text-cyan-400" /> HRTi katalog
            </h2>
            {authenticated && cdmReady && (
              <span className="badge flex items-center gap-1.5 bg-cyan-500/10 border-cyan-500/30 text-cyan-400 font-black px-2.5 py-1 text-[10px] tracking-wider rounded-md">
                <Lock className="w-3.5 h-3.5" /> Widevine L3 spreman
              </span>
            )}
            {authenticated && !cdmReady && (
              <span className="badge flex items-center gap-1.5 bg-amber-500/10 border-amber-500/30 text-amber-400 font-black px-2.5 py-1 text-[10px] tracking-wider rounded-md">
                Nedostaje device.wvd
              </span>
            )}
          </div>
          <p className="text-text-secondary text-sm">
            Pregledajte katalog, pretražujte sadržaj i preuzimajte filmove i epizode serija sa
            automatskom Widevine dekripcijom.
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
        <div className="md:col-span-2 flex flex-col gap-6">
          <div className="glass-panel p-6 rounded-xl border border-glass flex flex-col gap-4 glow-cyan-card glow-card-premium">
            <label className="m-0 flex items-center gap-2 text-xs font-bold text-text-secondary">
              <Link2 className="w-3.5 h-3.5" /> Direktan link ili Reference ID
            </label>
            <div className="smart-url-wrap">
              <Link2 className="smart-url-input-icon w-4 h-4" />
              <input
                type="text"
                className="smart-url-input"
                placeholder="https://hrti.hrt.hr/video/vod/... ili UUID"
                value={hrtiUrlInput}
                onChange={(e) => setHrtiUrlInput(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && resolveHrtiUrl()}
              />
              <button
                type="button"
                className="ytdlp-url-analyze-btn"
                onClick={() => void resolveHrtiUrl()}
                disabled={hrtiLoadingItems || !hrtiUrlInput.trim()}
              >
                {hrtiLoadingItems ? (
                  <Loader2 size={16} className="animate-spin" />
                ) : (
                  <Search size={16} />
                )}
                Otvori
              </button>
            </div>
          </div>

          <div className="glass-panel p-6 rounded-xl border border-glass flex flex-col md:flex-row gap-4 justify-between items-center glow-cyan-card glow-card-premium">
            <div className="flex items-center gap-3 w-full md:w-auto">
              <label className="m-0 text-xs text-text-secondary font-bold whitespace-nowrap">
                Kategorija:
              </label>
              <CustomSelect
                value={selectedCat}
                options={categoryOptions}
                onChange={(val) => {
                  setSelectedCat(val);
                  void fetchHrtiCategoryItems(val, 1);
                }}
                formatLabel={formatCategory}
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
                style={cssVars({
                  "--focused-border": "#06b6d4",
                  "--focused-glow": "rgba(6,182,212,0.25)",
                })}
              />
              <button
                type="button"
                onClick={() => void searchHrti()}
                className="btn btn-premium-primary absolute right-1.5 top-1.5 bottom-1.5 h-auto py-1 px-4 text-xs font-bold"
                style={cssVars({
                  "--btn-grad-start": "#06b6d4",
                  "--btn-grad-end": "#0891b2",
                  "--btn-glow": "rgba(6,182,212,0.25)",
                  "--btn-glow-hover": "rgba(6,182,212,0.45)",
                  height: "calc(100% - 6px)",
                  display: "flex",
                  alignItems: "center",
                })}
              >
                Pretraži
              </button>
            </div>
          </div>

          <div className="glass-panel p-8 rounded-xl border border-glass min-h-96 relative glow-cyan-card glow-card-premium">
            {hrtiLoadingItems && (
              <div className="absolute inset-0 bg-black/40 flex items-center justify-center rounded-xl z-10">
                <Loader2 className="w-12 h-12 text-cyan-500 animate-spin" />
              </div>
            )}

            {viewMode === "series" && selectedHrtiSeries ? (
              <div className="flex flex-col gap-6">
                <div className="flex justify-between items-center flex-wrap gap-3">
                  <button
                    type="button"
                    onClick={backToCatalog}
                    className="btn btn-secondary text-xs py-2 px-4"
                  >
                    ← Nazad na katalog
                  </button>
                  <div className="flex items-center gap-3">
                    <label className="text-[10px] font-bold text-text-muted m-0">WORKERS:</label>
                    <CustomSelect
                      value={String(hrtiWorkers)}
                      options={["8", "16", "24", "32"]}
                      onChange={(v) => setHrtiWorkers(Number(v))}
                      formatLabel={(v) => v}
                    />
                  </div>
                </div>

                <HrtiSeasonList
                  seriesTitle={selectedHrtiSeries.title}
                  seasons={hrtiSeriesSeasons}
                  episodes={catItems}
                  selectedEpisodes={selectedHrtiEpisodes}
                  setSelectedEpisodes={setSelectedHrtiEpisodes}
                />

                <button
                  type="button"
                  className="smart-cta-btn smart-cta-hrti w-full"
                  disabled={!canDownload || hrtiSubmitting || selectedHrtiEpisodes.length === 0}
                  onClick={() => void confirmHrtiBatchDownload()}
                >
                  {hrtiSubmitting ? (
                    <Loader2 className="w-5 h-5 animate-spin" />
                  ) : (
                    <Download className="w-5 h-5" />
                  )}
                  {hrtiSubmitting ? "Slanje..." : batchLabel}
                </button>
              </div>
            ) : (
              <>
                <h3 className="font-extrabold text-xl mb-6 text-white">Sadržaj na HRTi</h3>

                {hrtiLoadError && (
                  <div className="mb-4 px-4 py-3 rounded-lg border border-red-500/30 bg-red-500/10 text-sm text-red-300">
                    {hrtiLoadError}
                  </div>
                )}

                {catItems.length === 0 && !hrtiLoadingItems ? (
                  <div className="flex flex-col items-center justify-center p-20 text-center">
                    <AlertCircle className="w-12 h-12 text-text-muted mb-4" />
                    <p className="text-text-secondary font-semibold">
                      {hrtiLoadError ? "Učitavanje nije uspelo." : "Nema pronađenog sadržaja."}
                    </p>
                  </div>
                ) : (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    {catItems.map((item: HrtiItem) => {
                      const isMovie = item.type === "movie";
                      const cardGlow = isMovie
                        ? "rgba(6, 182, 212, 0.25)"
                        : "rgba(147, 51, 234, 0.25)";
                      return (
                        <div
                          key={item.id}
                          className="netflix-card group"
                          style={cssVars({ "--card-glow": cardGlow })}
                          onClick={() => {
                            if (!canDownload) return;
                            if (item.type === "series") {
                              void fetchHrtiSeriesEpisodes(item.id, item.title);
                            } else {
                              startHrtiDownload(item.id, item.title);
                            }
                          }}
                        >
                          <div
                            className={`absolute inset-0 w-full h-full flex items-center justify-center overflow-hidden transition-transform duration-700 group-hover:scale-105 ${isMovie ? "hrti-thumbnail-movie" : "hrti-thumbnail-series"}`}
                          >
                            {item.thumbnail ? (
                              <img
                                src={item.thumbnail}
                                alt={item.title}
                                className="w-full h-full object-cover"
                              />
                            ) : isMovie ? (
                              <Film className="w-16 h-16 opacity-10 text-indigo-300 transform -rotate-12 transition-transform duration-500 group-hover:scale-110 group-hover:rotate-0" />
                            ) : (
                              <Tv className="w-16 h-16 opacity-10 text-purple-300 transform rotate-12 transition-transform duration-500 group-hover:scale-110 group-hover:rotate-0" />
                            )}
                          </div>

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

                          <div className="netflix-card-play">
                            {item.type === "series" ? (
                              <List className="w-5 h-5 text-indigo-900" />
                            ) : (
                              <Download className="w-5 h-5 text-cyan-900" />
                            )}
                          </div>

                          <div className="netflix-card-content">
                            <h4 className="font-extrabold text-white text-base leading-snug line-clamp-2 group-hover:text-cyan-200 transition-colors">
                              {item.title}
                            </h4>
                            <p className="text-[9px] text-text-muted font-mono mt-1 select-all truncate">
                              {item.id}
                            </p>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}

                {catTotalPages > 1 && (
                  <div className="flex justify-center items-center gap-4 mt-10">
                    <button
                      type="button"
                      disabled={catPage <= 1}
                      onClick={() => void fetchHrtiCategoryItems(selectedCat, catPage - 1)}
                      className="btn btn-secondary text-xs py-2"
                    >
                      Prethodna
                    </button>
                    <span className="text-sm font-bold text-text-secondary">
                      Stranica {catPage} od {catTotalPages}
                    </span>
                    <button
                      type="button"
                      disabled={catPage >= catTotalPages}
                      onClick={() => void fetchHrtiCategoryItems(selectedCat, catPage + 1)}
                      className="btn btn-secondary text-xs py-2"
                    >
                      Sledeća
                    </button>
                  </div>
                )}
              </>
            )}
          </div>
        </div>

        <HrtiSidebar status={status} authenticated={authenticated} />
      </div>
    </div>
  );
}
