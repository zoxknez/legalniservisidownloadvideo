import type { CSSProperties } from "react";
import { Clock, Eye, Heart, User } from "lucide-react";
import type { SmartDetectData } from "../../types/app";
import { toggleYtdlpSubsLang } from "../../hooks/domains/ytdlpShared";
import { YTDLP_THEME, type YtdlpTheme } from "./ytdlpTheme";

const metaPillStyle: CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  gap: 4,
  fontSize: "0.72rem",
  fontWeight: 700,
  color: "var(--text-secondary)",
  background: "rgba(255,255,255,0.04)",
  border: "1px solid rgba(255,255,255,0.07)",
  borderRadius: 6,
  padding: "3px 8px",
};

function formatCount(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(0)}K`;
  return String(n);
}

export interface YtdlpPreviewExtrasProps {
  data: SmartDetectData;
  subs?: string;
  setSubs?: (v: string) => void;
  theme?: YtdlpTheme;
  showGenericBanner?: boolean;
}

export function YtdlpPreviewExtras({
  data,
  subs = "",
  setSubs,
  theme = YTDLP_THEME,
  showGenericBanner = true,
}: YtdlpPreviewExtrasProps) {
  const manual = data.available_subtitles || [];
  const auto = data.available_auto_subtitles || [];
  const showSubs = setSubs && (manual.length > 0 || auto.length > 0);

  return (
    <>
      {showGenericBanner && data.generic_url && !data.metadata_partial && (
        <div className="mt-2 px-3 py-2 rounded-lg border border-blue-500/25 bg-blue-500/10 text-[11px] font-bold text-blue-300">
          Link nije prepoznat kao poznati servis — koristi se univerzalni yt-dlp preuzimač.
        </div>
      )}
      {data.metadata_partial && (
        <div className="mt-2 px-3 py-2 rounded-lg border border-amber-500/30 bg-amber-500/10 text-[11px] font-bold text-amber-300">
          Metapodaci nisu u potpunosti dostupni — preuzimanje je i dalje moguće. Probajte cookies
          ili impersonate u konzoli ispod.
        </div>
      )}

      {(data.duration_str ||
        data.uploader ||
        data.view_count != null ||
        data.like_count != null ||
        data.upload_date) && (
        <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginTop: 10 }}>
          {data.duration_str && (
            <span style={metaPillStyle}>
              <Clock style={{ width: 11, height: 11 }} />
              {data.duration_str}
            </span>
          )}
          {data.uploader && (
            <span style={metaPillStyle}>
              <User style={{ width: 11, height: 11 }} />
              {data.uploader}
            </span>
          )}
          {data.view_count != null && (
            <span style={metaPillStyle}>
              <Eye style={{ width: 11, height: 11 }} />
              {formatCount(data.view_count)} pregleda
            </span>
          )}
          {data.like_count != null && (
            <span style={metaPillStyle}>
              <Heart style={{ width: 11, height: 11 }} />
              {formatCount(data.like_count)} lajkova
            </span>
          )}
          {data.upload_date && <span style={metaPillStyle}>{data.upload_date}</span>}
        </div>
      )}

      {showSubs && (
        <div className="mt-3 flex flex-col gap-2">
          <span className="text-[10px] font-bold text-text-muted uppercase tracking-wider">
            Dostupni titlovi — klik za izbor
          </span>
          <div className="flex flex-wrap gap-1.5">
            {manual.map((lang) => {
              const isSel = subs
                .split(",")
                .map((s) => s.trim().toLowerCase())
                .includes(lang.toLowerCase());
              return (
                <button
                  key={`m-${lang}`}
                  type="button"
                  onClick={() => setSubs!(toggleYtdlpSubsLang(subs, lang))}
                  className={`px-2.5 py-1 rounded text-[10px] font-bold border transition-all ${
                    isSel
                      ? "bg-blue-500/20 text-blue-400 border-blue-500/40"
                      : "bg-white/[0.02] text-text-secondary border-white/[0.04] hover:bg-white/[0.05]"
                  }`}
                >
                  {lang.toUpperCase()}
                </button>
              );
            })}
            {auto.map((lang) => {
              const isSel = subs
                .split(",")
                .map((s) => s.trim().toLowerCase())
                .includes(lang.toLowerCase());
              return (
                <button
                  key={`a-${lang}`}
                  type="button"
                  onClick={() => setSubs!(toggleYtdlpSubsLang(subs, lang))}
                  className={`px-2.5 py-1 rounded text-[10px] font-bold border transition-all ${
                    isSel
                      ? "bg-amber-500/20 text-amber-400 border-amber-500/40"
                      : "bg-white/[0.02] text-text-secondary border-white/[0.04] hover:bg-white/[0.05]"
                  }`}
                  title="Automatski generisani titlovi"
                >
                  auto-{lang.toUpperCase()}
                </button>
              );
            })}
          </div>
        </div>
      )}
    </>
  );
}

export interface YtdlpPreviewHeaderProps {
  data: SmartDetectData;
  subs?: string;
  setSubs?: (v: string) => void;
  theme?: YtdlpTheme;
}

export function YtdlpPreviewHeader({
  data,
  subs = "",
  setSubs,
  theme = YTDLP_THEME,
}: YtdlpPreviewHeaderProps) {
  return (
    <div
      className="smart-preview-header"
      style={{ borderBottom: "1px solid rgba(255,255,255,0.05)", paddingBottom: 20 }}
    >
      <div className="smart-preview-thumb" style={{ borderColor: `${theme.color}30` }}>
        {data.thumbnail ? (
          <img src={data.thumbnail} alt={data.title} />
        ) : (
          <span style={{ fontSize: "2rem" }}>{theme.emoji}</span>
        )}
      </div>
      <div style={{ flex: 1 }}>
        <div
          className="smart-preview-badge"
          style={{
            background: `${theme.color}18`,
            color: theme.color,
            border: `1px solid ${theme.color}35`,
          }}
        >
          {theme.emoji} {theme.name} · {data.mode?.toUpperCase()}
          {data.playlist_count != null && data.mode === "playlist" && (
            <span className="opacity-80"> · {data.playlist_count} stavki</span>
          )}
        </div>
        <h3 className="smart-preview-title">{data.title}</h3>

        {data.description && <p className="smart-preview-desc">{data.description}</p>}

        <YtdlpPreviewExtras data={data} subs={subs} setSubs={setSubs} theme={theme} />
      </div>
    </div>
  );
}
