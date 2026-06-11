import { useState } from "react";
import { Check, ChevronDown, ChevronRight, FileText, Lock, X } from "lucide-react";
import type { VoyoEpisode, VoyoSeason } from "../../types/app";
import {
  defaultVoyoEpisodeIds,
  voyoCatalogDrmHint,
  voyoIsHardBlocked,
  voyoIsSoftHint,
} from "../../lib/voyoDrm";
import { cssVars } from "../../utils/cssVars";

export function nonDrmVoyoEpisodeIds(
  episodes: VoyoEpisode[],
  ignoreCatalogDrmHint = false,
): number[] {
  return defaultVoyoEpisodeIds(episodes, ignoreCatalogDrmHint);
}

/** Epizode za Pametno preuzimanje (flat lista). */
export function nonDrmSmartEpisodeIds(
  episodes: (VoyoEpisode & { id: number | string })[],
  ignoreCatalogDrmHint = false,
): (number | string)[] {
  return defaultVoyoEpisodeIds(
    episodes as VoyoEpisode[],
    ignoreCatalogDrmHint,
  ) as (number | string)[];
}

export function VoyoSeasonList({
  voyoSeriesData,
  selectedVoyoEpisodes,
  setSelectedVoyoEpisodes,
  showHeader = true,
  ignoreCatalogDrmHint = false,
}: {
  voyoSeriesData: { title: string; description: string; seasons?: VoyoSeason[]; episodes: VoyoEpisode[] };
  selectedVoyoEpisodes: number[];
  setSelectedVoyoEpisodes: (ids: number[]) => void;
  showHeader?: boolean;
  ignoreCatalogDrmHint?: boolean;
}) {
  const seasons = voyoSeriesData.seasons ?? [];
  const hasSeason = seasons.length > 0;
  const [expandedSeasons, setExpandedSeasons] = useState<Set<number>>(
    () => new Set(seasons.map((s) => s.season)),
  );

  const toggleSeason = (sn: number) => {
    setExpandedSeasons((prev) => {
      const next = new Set(prev);
      if (next.has(sn)) next.delete(sn);
      else next.add(sn);
      return next;
    });
  };

  const isBlocked = (ep: VoyoEpisode) => voyoIsHardBlocked(ep);

  const toggleEp = (ep: VoyoEpisode) => {
    if (isBlocked(ep)) return;
    const id = ep.id;
    if (selectedVoyoEpisodes.includes(id)) {
      setSelectedVoyoEpisodes(selectedVoyoEpisodes.filter((x) => x !== id));
    } else {
      setSelectedVoyoEpisodes([...selectedVoyoEpisodes, id]);
    }
  };

  const selectableEps = (eps: VoyoEpisode[]) =>
    eps.filter(
      (e) => !isBlocked(e) && (ignoreCatalogDrmHint || !voyoCatalogDrmHint(e)),
    );

  const toggleAllSeason = (eps: VoyoEpisode[]) => {
    const selectable = selectableEps(eps);
    const ids = selectable.map((e) => e.id);
    const allChecked = ids.length > 0 && ids.every((id) => selectedVoyoEpisodes.includes(id));
    if (allChecked) {
      setSelectedVoyoEpisodes(selectedVoyoEpisodes.filter((id) => !ids.includes(id)));
    } else {
      setSelectedVoyoEpisodes([...new Set([...selectedVoyoEpisodes, ...ids])]);
    }
  };

  const selectAllDefault = () => {
    setSelectedVoyoEpisodes(defaultVoyoEpisodeIds(voyoSeriesData.episodes, ignoreCatalogDrmHint));
  };

  const renderEpisode = (ep: VoyoEpisode) => {
    const blocked = isBlocked(ep);
    const softHint = voyoIsSoftHint(ep, ignoreCatalogDrmHint);
    const checked = !blocked && selectedVoyoEpisodes.includes(ep.id);
    return (
      <div
        key={ep.id}
        className={`custom-checkbox-wrap ${blocked ? "opacity-45 cursor-not-allowed" : softHint ? "opacity-90" : "cursor-pointer"}`}
        style={cssVars({
          borderRadius: 8,
          padding: "8px 10px",
          "--checkbox-bg": "#ea580c",
          "--checkbox-glow": "rgba(249, 115, 22, 0.3)",
        })}
        onClick={() => toggleEp(ep)}
        title={
          blocked
            ? ep.stream_reason || "Stream nije dostupan za preuzimanje"
            : softHint
              ? "Zaštićeno u katalogu — možete probati preuzimanje"
              : undefined
        }
      >
        <div className={`custom-checkbox-box ${checked ? "checked" : ""}`}>
          <svg className="custom-checkbox-check" viewBox="0 0 10 10" fill="none" stroke="white" strokeWidth="2">
            <polyline points="1.5 5 4 7.5 8.5 2" />
          </svg>
        </div>
        <span className="font-extrabold text-[10px] tracking-wider uppercase bg-orange-500/10 text-orange-400 border border-orange-500/20 px-2 py-0.5 rounded min-w-16 text-center">
          S{ep.season.toString().padStart(2, "0")}E{ep.episode.toString().padStart(2, "0")}
        </span>
        <span className="flex-1 truncate text-white text-sm font-semibold">{ep.title}</span>
        <span className="text-xs text-text-muted">{ep.length_mins}m</span>
        {blocked && (
          <span title="Nedostupan stream">
            <Lock className="w-3.5 h-3.5 text-red-400" />
          </span>
        )}
        {!blocked && softHint && (
          <span title="Katalog DRM hint">
            <Lock className="w-3.5 h-3.5 text-amber-500" />
          </span>
        )}
        {ep.has_subs && (
          <span title="Titlovi u streamu (ugrađeni u HLS)">
            <FileText className="w-3.5 h-3.5 text-indigo-400" />
          </span>
        )}
      </div>
    );
  };

  const hintCount = voyoSeriesData.episodes.filter((e) => voyoCatalogDrmHint(e)).length;
  const blockedCount = voyoSeriesData.episodes.filter((e) => voyoIsHardBlocked(e)).length;

  return (
    <div className={showHeader ? "border-t border-glass pt-6 flex flex-col gap-4" : "flex flex-col gap-4"}>
      {showHeader && (
        <div>
          <h3 className="font-extrabold text-lg text-orange-500">{voyoSeriesData.title}</h3>
          <p className="text-xs text-text-secondary mt-1">{voyoSeriesData.description}</p>
          {blockedCount > 0 && (
            <p className="text-[11px] font-bold text-red-400 mt-2">
              {blockedCount} epizoda sa nedostupnim streamom (Widevine ili greška probe).
            </p>
          )}
          {hintCount > 0 && !ignoreCatalogDrmHint && (
            <p className="text-[11px] font-bold text-amber-400 mt-2">
              {hintCount} epizoda označeno u katalogu kao zaštićeno — podrazumevano nisu označene, ali možete ih izabrati.
            </p>
          )}
        </div>
      )}

      <div>
        <div className="flex justify-between items-center mb-2">
          <label className="m-0 font-bold text-xs">
            {hasSeason
              ? `${seasons.length} sezona — ${voyoSeriesData.episodes.length} epizoda`
              : `Epizode u seriji (${voyoSeriesData.episodes.length})`}
          </label>
          <div className="flex gap-2">
            <button
              type="button"
              className="text-[10px] uppercase font-extrabold text-orange-400 bg-orange-500/5 hover:bg-orange-500/15 border border-orange-500/10 hover:border-orange-500/20 px-2 py-1 rounded transition-all flex items-center gap-1"
              onClick={selectAllDefault}
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

        <div className="max-h-80 overflow-y-auto border border-glass rounded-lg bg-black/40 p-2 flex flex-col gap-1">
          {hasSeason
            ? seasons.map((season) => {
                const isOpen = expandedSeasons.has(season.season);
                const seasonEps = season.episodes;
                const selectable = selectableEps(seasonEps);
                const checkedCount = selectable.filter((e) => selectedVoyoEpisodes.includes(e.id)).length;
                const allChecked = selectable.length > 0 && checkedCount === selectable.length;

                return (
                  <div key={season.season}>
                    <div
                      className="flex items-center gap-2 px-2 py-2 rounded-lg cursor-pointer hover:bg-white/[0.04] transition-colors"
                      onClick={() => toggleSeason(season.season)}
                    >
                      {isOpen ? (
                        <ChevronDown className="w-4 h-4 text-orange-400" />
                      ) : (
                        <ChevronRight className="w-4 h-4 text-text-muted" />
                      )}
                      <span className="font-extrabold text-sm text-white flex-1">Sezona {season.season}</span>
                      <span className="text-[10px] text-text-muted font-semibold">
                        {checkedCount}/{selectable.length}
                      </span>
                      <button
                        type="button"
                        className={`text-[10px] uppercase font-extrabold px-2 py-0.5 rounded transition-all ${allChecked ? "text-text-muted bg-white/[0.02] border border-white/[0.05]" : "text-orange-400 bg-orange-500/10 border border-orange-500/20"}`}
                        onClick={(e) => {
                          e.stopPropagation();
                          toggleAllSeason(seasonEps);
                        }}
                      >
                        {allChecked ? "Odznači" : "Označi"}
                      </button>
                    </div>
                    {isOpen && <div className="flex flex-col gap-1 ml-4 mb-2">{seasonEps.map(renderEpisode)}</div>}
                  </div>
                );
              })
            : voyoSeriesData.episodes.map(renderEpisode)}
        </div>
      </div>
    </div>
  );
}
