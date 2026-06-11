import { useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";
import type { HrtiItem, HrtiSeason } from "../../types/app";
import { cssVars } from "../../utils/cssVars";

export function HrtiSeasonList({
  seriesTitle,
  seasons,
  episodes,
  selectedEpisodes,
  setSelectedEpisodes,
}: {
  seriesTitle: string;
  seasons: HrtiSeason[];
  episodes: HrtiItem[];
  selectedEpisodes: string[];
  setSelectedEpisodes: (ids: string[]) => void;
}) {
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

  const toggleEp = (id: string) => {
    if (selectedEpisodes.includes(id)) {
      setSelectedEpisodes(selectedEpisodes.filter((x) => x !== id));
    } else {
      setSelectedEpisodes([...selectedEpisodes, id]);
    }
  };

  const epsForSeason = (sn: number) =>
    episodes.filter((ep) => (ep.season ?? 1) === sn);

  const toggleAllSeason = (sn: number) => {
    const ids = epsForSeason(sn).map((e) => e.id);
    const allChecked = ids.length > 0 && ids.every((id) => selectedEpisodes.includes(id));
    if (allChecked) {
      setSelectedEpisodes(selectedEpisodes.filter((id) => !ids.includes(id)));
    } else {
      setSelectedEpisodes([...new Set([...selectedEpisodes, ...ids])]);
    }
  };

  const selectAll = () => setSelectedEpisodes(episodes.map((e) => e.id));
  const clearAll = () => setSelectedEpisodes([]);

  const renderEpisode = (ep: HrtiItem) => {
    const checked = selectedEpisodes.includes(ep.id);
    const sn = ep.season ?? 1;
    const en = ep.episode ?? 0;
    return (
      <div
        key={ep.id}
        className="custom-checkbox-wrap"
        style={cssVars({
          borderRadius: 8,
          padding: "8px 10px",
          "--checkbox-bg": "#06b6d4",
          "--checkbox-glow": "rgba(6, 182, 212, 0.3)",
        })}
        onClick={() => toggleEp(ep.id)}
      >
        <div className={`custom-checkbox-box ${checked ? "checked" : ""}`}>
          <svg className="custom-checkbox-check" viewBox="0 0 10 10" fill="none" stroke="white" strokeWidth="2">
            <polyline points="1.5 5 4 7.5 8.5 2" />
          </svg>
        </div>
        <span className="font-extrabold text-[10px] tracking-wider uppercase bg-cyan-500/10 text-cyan-300 border border-cyan-500/20 px-2 py-0.5 rounded min-w-16 text-center">
          S{String(sn).padStart(2, "0")}E{String(en).padStart(2, "0")}
        </span>
        <span className="text-sm font-semibold text-white flex-1 truncate">{ep.title}</span>
      </div>
    );
  };

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <h3 className="font-extrabold text-lg text-white">{seriesTitle}</h3>
        <div className="flex gap-3 text-[11px] font-bold">
          <button type="button" className="text-cyan-400 hover:underline" onClick={selectAll}>
            Označi sve ({episodes.length})
          </button>
          <span className="text-text-muted">|</span>
          <button type="button" className="text-text-muted hover:text-white" onClick={clearAll}>
            Odznači sve
          </button>
        </div>
      </div>

      {hasSeason ? (
        <div className="flex flex-col gap-2">
          {seasons.map((season) => {
            const sn = season.season;
            const expanded = expandedSeasons.has(sn);
            const seasonEps = epsForSeason(sn);
            const selectedInSeason = seasonEps.filter((e) => selectedEpisodes.includes(e.id)).length;
            return (
              <div key={sn} className="glass-card p-3 rounded-lg border border-glass">
                <div
                  className="flex items-center justify-between cursor-pointer"
                  onClick={() => toggleSeason(sn)}
                >
                  <div className="flex items-center gap-2">
                    {expanded ? (
                      <ChevronDown className="w-4 h-4 text-cyan-400" />
                    ) : (
                      <ChevronRight className="w-4 h-4 text-text-muted" />
                    )}
                    <span className="font-extrabold text-sm text-white">
                      {season.title || `Sezona ${sn}`}
                    </span>
                    <span className="text-[10px] text-text-muted">
                      ({selectedInSeason}/{seasonEps.length})
                    </span>
                  </div>
                  <button
                    type="button"
                    className="text-[10px] font-bold text-cyan-400 hover:underline"
                    onClick={(e) => {
                      e.stopPropagation();
                      toggleAllSeason(sn);
                    }}
                  >
                    Označi sezonu
                  </button>
                </div>
                {expanded && (
                  <div className="flex flex-col gap-1.5 mt-3 pl-1">{seasonEps.map(renderEpisode)}</div>
                )}
              </div>
            );
          })}
        </div>
      ) : (
        <div className="flex flex-col gap-1.5">{episodes.map(renderEpisode)}</div>
      )}
    </div>
  );
}
