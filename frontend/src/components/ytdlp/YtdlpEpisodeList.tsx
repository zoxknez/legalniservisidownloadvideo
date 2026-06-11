import { Lock } from "lucide-react";
import type { SmartDetectData, SmartEpisode } from "../../types/app";
import { YTDLP_THEME, type YtdlpTheme } from "./ytdlpTheme";

export interface YtdlpEpisodeListProps {
  data: SmartDetectData;
  selectedEpisodes: (number | string)[];
  setSelectedEpisodes: (ids: (number | string)[]) => void;
  theme?: YtdlpTheme;
}

export function YtdlpEpisodeList({
  data,
  selectedEpisodes,
  setSelectedEpisodes,
  theme = YTDLP_THEME,
}: YtdlpEpisodeListProps) {
  if (!data.episodes?.length) return null;

  const isPlaylist = data.mode === "playlist";
  const label = isPlaylist
    ? `Stavke plejliste (${selectedEpisodes.length}/${data.episodes.length})`
    : `Epizode (${selectedEpisodes.length}/${data.episodes.length})`;

  return (
    <div>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: 10,
        }}
      >
        <label style={{ margin: 0 }}>{label}</label>
        <div style={{ display: "flex", gap: 12 }}>
          <button
            type="button"
            style={{
              fontSize: "0.72rem",
              fontWeight: 700,
              color: theme.color,
              background: "none",
              border: "none",
              cursor: "pointer",
            }}
            onClick={() =>
              setSelectedEpisodes(data.episodes!.map((e: SmartEpisode) => e.id))
            }
          >
            Označi sve
          </button>
          <span style={{ color: "var(--text-muted)" }}>|</span>
          <button
            type="button"
            style={{
              fontSize: "0.72rem",
              fontWeight: 700,
              color: "var(--text-muted)",
              background: "none",
              border: "none",
              cursor: "pointer",
            }}
            onClick={() => setSelectedEpisodes([])}
          >
            Odznači sve
          </button>
        </div>
      </div>
      <div className="smart-ep-list">
        {data.episodes.map((ep: SmartEpisode, idx: number) => {
          const checked = selectedEpisodes.includes(ep.id);
          return (
            <div
              key={ep.id ?? idx}
              className={`smart-ep-item ${checked ? "selected" : ""}`}
              onClick={() =>
                setSelectedEpisodes(
                  checked
                    ? selectedEpisodes.filter((id) => id !== ep.id)
                    : [...selectedEpisodes, ep.id],
                )
              }
              style={
                checked
                  ? { borderLeft: `3px solid ${theme.color}80` }
                  : { borderLeft: "3px solid transparent" }
              }
            >
              <div
                className={`custom-checkbox-box ${checked ? "checked" : ""}`}
                style={
                  checked ? { background: theme.color, borderColor: theme.color } : {}
                }
              >
                <svg
                  className="custom-checkbox-check"
                  viewBox="0 0 10 10"
                  fill="none"
                  stroke="white"
                  strokeWidth="2"
                >
                  <polyline points="1.5 5 4 7.5 8.5 2" />
                </svg>
              </div>
              {ep.season && ep.episode && (
                <span
                  style={{
                    fontSize: "0.72rem",
                    fontWeight: 800,
                    color: theme.color,
                    minWidth: 52,
                    flexShrink: 0,
                  }}
                >
                  S{String(ep.season).padStart(2, "0")}E{String(ep.episode).padStart(2, "0")}
                </span>
              )}
              <span
                style={{
                  flex: 1,
                  fontSize: "0.82rem",
                  color: "white",
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  whiteSpace: "nowrap",
                }}
              >
                {ep.title}
              </span>
              {(ep.length_mins ?? 0) > 0 && (
                <span style={{ fontSize: "0.7rem", color: "var(--text-muted)", flexShrink: 0 }}>
                  {ep.length_mins}m
                </span>
              )}
              {ep.drm && (
                <Lock style={{ width: 12, height: 12, color: "#f59e0b", flexShrink: 0 }} />
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
