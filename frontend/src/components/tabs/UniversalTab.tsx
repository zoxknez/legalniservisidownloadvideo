import type { CSSProperties } from "react";
import {
  Download,
  Globe,
  Loader2,
  Lock,
  Search,
  X,
  Zap,
} from "lucide-react";
import { useYtdlpTab } from "../../hooks/domains/useYtdlpTab";
import { YtdlpDownloadPanel } from "../ytdlp/YtdlpDownloadPanel";
import type { SmartEpisode } from "../../types/app";
import { cssVars } from "../../utils/cssVars";

const THEME = {
  color: "#3b82f6",
  glow: "rgba(59,130,246,0.08)",
  emoji: "🌐",
  name: "Univerzalno",
};

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

export function UniversalTab() {
  const {
    ytdlpUrl,
    setYtdlpUrl,
    ytdlpLoading,
    ytdlpData,
    ytdlpSelectedEpisodes,
    setYtdlpSelectedEpisodes,
    ytdlpResolution,
    setYtdlpResolution,
    ytdlpSubs,
    setYtdlpSubs,
    ytdlpAudioOnly,
    setYtdlpAudioOnly,
    ytdlpUseAria2,
    setYtdlpUseAria2,
    ytdlpCookiesBrowser,
    setYtdlpCookiesBrowser,
    ytdlpImpersonate,
    setYtdlpImpersonate,
    ytdlpProxy,
    setYtdlpProxy,
    ytdlpGeoBypass,
    setYtdlpGeoBypass,
    ytdlpEmbedThumbnail,
    setYtdlpEmbedThumbnail,
    ytdlpEmbedMetadata,
    setYtdlpEmbedMetadata,
    ytdlpLimitRate,
    setYtdlpLimitRate,
    ytdlpHardsub,
    setYtdlpHardsub,
    ytdlpSponsorblockMode,
    setYtdlpSponsorblockMode,
    ytdlpSplitChapters,
    setYtdlpSplitChapters,
    ytdlpDownloadPlaylist,
    setYtdlpDownloadPlaylist,
    ytdlpPlaylistItems,
    setYtdlpPlaylistItems,
    ytdlpFormatSpec,
    setYtdlpFormatSpec,
    ytdlpExtractorArgs,
    setYtdlpExtractorArgs,
    ytdlpCookiesConfigured,
    ytdlpCookiesUploading,
    uploadYtdlpCookies,
    clearYtdlpCookies,
    ytdlpSubmitting,
    subsOpen,
    setSubsOpen,
    analyzeYtdlpUrl,
    debouncedAnalyze,
    startYtdlpDownload,
    cancelYtdlpPreview,
    status,
  } = useYtdlpTab();

  const ytdlpSvc = status?.services?.ytdlp;
  const ready = ytdlpSvc?.ready ?? ytdlpSvc?.authenticated ?? true;
  const ver = (ytdlpSvc as { ytdlp_version?: string } | undefined)?.ytdlp_version;
  const svcError = (ytdlpSvc as { error?: string } | undefined)?.error;

  return (
    <div key="ytdlp" className="tab-content tab-content-ytdlp">
      <div className="tab-page-header tab-header-ytdlp mb-8">
        <div
          className="tab-page-header-icon"
          style={{ background: "linear-gradient(135deg, #3b82f6, #2563eb)" }}
        >
          <Globe style={{ width: 24, height: 24, color: "white" }} />
        </div>
        <div style={{ flex: 1 }}>
          <div className="flex items-center justify-between flex-wrap gap-2">
            <h2 className="text-2xl font-extrabold text-white mb-1 flex items-center gap-2.5">
              <Globe className="w-6 h-6 text-blue-400" /> Univerzalno (yt-dlp)
            </h2>
            <span
              className={`badge flex items-center gap-1.5 font-black px-2.5 py-1 text-[10px] tracking-wider rounded-md ${
                ready
                  ? "bg-blue-500/10 border-blue-500/30 text-blue-400"
                  : "bg-amber-500/10 border-amber-500/30 text-amber-400"
              }`}
            >
              <Zap className="w-3.5 h-3.5" />
              {ready ? (ver ? `yt-dlp ${ver}` : "Spremno") : svcError || "Proverite Node.js"}
            </span>
          </div>
          <p className="text-text-secondary text-sm">
            Preuzimanje sa YouTube, X, TikTok, Facebook, Vimeo i hiljada drugih sajtova preko yt-dlp.
          </p>
          <p className="text-xs text-text-muted mt-1.5">
            Primer:{" "}
            <code className="font-mono text-blue-400 bg-white/[0.04] px-1.5 py-0.5 rounded">
              https://www.youtube.com/watch?v=...
            </code>
          </p>
        </div>
      </div>

      <div className="glass-panel p-6 md:p-8 rounded-xl border border-glass flex flex-col gap-6 glow-card-premium mb-6">
        <div>
          <label>URL videa ili plejliste</label>
          <div className="password-wrapper">
            <Globe className="absolute left-4 text-text-muted w-4 h-4" />
            <input
              type="text"
              placeholder="Nalepite link — analiza počinje automatski"
              value={ytdlpUrl}
              onChange={(e) => {
                setYtdlpUrl(e.target.value);
                debouncedAnalyze(e.target.value);
              }}
              onKeyDown={(e) => e.key === "Enter" && analyzeYtdlpUrl(ytdlpUrl)}
              className="input-premium pl-11"
              style={cssVars({
                "--focused-border": "#3b82f6",
                "--focused-glow": "rgba(59,130,246,0.25)",
              })}
            />
          </div>
          <div className="flex flex-wrap gap-2 mt-3">
            <button
              type="button"
              className="smart-url-analyze-btn"
              style={{ background: "linear-gradient(135deg, #3b82f6, #2563eb)" }}
              onClick={() => analyzeYtdlpUrl(ytdlpUrl)}
              disabled={ytdlpLoading || ytdlpSubmitting || !ytdlpUrl.trim()}
            >
              {ytdlpLoading ? (
                <Loader2 style={{ width: 16, height: 16, animation: "spin 1s linear infinite" }} />
              ) : (
                <Search style={{ width: 16, height: 16 }} />
              )}
              {ytdlpLoading ? "Analizira..." : "Analiziraj"}
            </button>
            {ytdlpData && (
              <button
                type="button"
                className="text-[10px] font-extrabold uppercase text-text-muted hover:text-white px-3 py-2 rounded border border-white/10"
                onClick={cancelYtdlpPreview}
              >
                <X className="w-3 h-3 inline mr-1" />
                Poništi
              </button>
            )}
          </div>
        </div>

        <div className="flex flex-wrap gap-2">
          <span className="text-[10px] text-text-muted font-bold self-center mr-1">PODRŽANO:</span>
          {["YouTube", "X / Twitter", "TikTok", "Facebook", "Vimeo", "SoundCloud", "ostali..."].map(
            (p) => (
              <span
                key={p}
                className="smart-platform-pill text-blue-400 border border-blue-500/20"
                style={{ background: "rgba(59,130,246,0.08)" }}
              >
                {p}
              </span>
            ),
          )}
        </div>
      </div>

      {ytdlpLoading && !ytdlpData && (
        <div
          className="smart-preview-panel"
          style={{
            borderColor: "rgba(59,130,246,0.2)",
            padding: 32,
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            gap: 16,
          }}
        >
          <Loader2
            style={{ width: 32, height: 32, color: "#3b82f6", animation: "spin 1s linear infinite" }}
          />
          <p className="text-sm font-bold text-white">Analiziramo link...</p>
          <p className="text-xs text-text-muted">Ekstrakcija metapodataka i dostupnih formata</p>
        </div>
      )}

      {ytdlpData && (
        <div
          className="smart-preview-panel"
          style={{
            borderColor: `${THEME.color}40`,
            boxShadow: `0 0 40px ${THEME.glow}, 0 4px 24px rgba(0,0,0,0.4)`,
          }}
        >
          <div
            className="smart-preview-header"
            style={{ borderBottom: "1px solid rgba(255,255,255,0.05)", paddingBottom: 20 }}
          >
            <div className="smart-preview-thumb" style={{ borderColor: `${THEME.color}30` }}>
              {ytdlpData.thumbnail ? (
                <img src={ytdlpData.thumbnail} alt={ytdlpData.title} />
              ) : (
                <span style={{ fontSize: "2rem" }}>{THEME.emoji}</span>
              )}
            </div>
            <div style={{ flex: 1 }}>
              <div
                className="smart-preview-badge"
                style={{
                  background: `${THEME.color}18`,
                  color: THEME.color,
                  border: `1px solid ${THEME.color}35`,
                }}
              >
                {THEME.emoji} {THEME.name} · {ytdlpData.mode?.toUpperCase()}
              </div>
              <h3 className="smart-preview-title">{ytdlpData.title}</h3>
              {ytdlpData.metadata_partial && (
                <div className="mt-2 px-3 py-2 rounded-lg border border-amber-500/30 bg-amber-500/10 text-[11px] font-bold text-amber-300">
                  Metapodaci nisu u potpunosti dostupni — preuzimanje je i dalje moguće.
                </div>
              )}
              {ytdlpData.description && (
                <p className="smart-preview-desc">{ytdlpData.description}</p>
              )}
              {(ytdlpData.duration_str ||
                ytdlpData.uploader ||
                ytdlpData.view_count != null ||
                ytdlpData.upload_date) && (
                <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginTop: 10 }}>
                  {ytdlpData.duration_str && (
                    <span style={metaPillStyle}>{ytdlpData.duration_str}</span>
                  )}
                  {ytdlpData.uploader && (
                    <span style={metaPillStyle}>{ytdlpData.uploader}</span>
                  )}
                  {ytdlpData.view_count != null && (
                    <span style={metaPillStyle}>
                      {ytdlpData.view_count >= 1_000_000
                        ? `${(ytdlpData.view_count / 1_000_000).toFixed(1)}M pregleda`
                        : ytdlpData.view_count >= 1_000
                          ? `${(ytdlpData.view_count / 1_000).toFixed(0)}K pregleda`
                          : `${ytdlpData.view_count} pregleda`}
                    </span>
                  )}
                  {ytdlpData.upload_date && (
                    <span style={metaPillStyle}>{ytdlpData.upload_date}</span>
                  )}
                </div>
              )}
            </div>
          </div>

          <div className="smart-preview-body">
            {ytdlpData.episodes && ytdlpData.episodes.length > 0 && (
              <div>
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    marginBottom: 10,
                  }}
                >
                  <label style={{ margin: 0 }}>
                    {ytdlpData.mode === "playlist"
                      ? `Stavke plejliste (${ytdlpSelectedEpisodes.length}/${ytdlpData.episodes.length})`
                      : `Epizode (${ytdlpSelectedEpisodes.length}/${ytdlpData.episodes.length})`}
                  </label>
                  <div style={{ display: "flex", gap: 12 }}>
                    <button
                      type="button"
                      style={{
                        fontSize: "0.72rem",
                        fontWeight: 700,
                        color: THEME.color,
                        background: "none",
                        border: "none",
                        cursor: "pointer",
                      }}
                      onClick={() =>
                        setYtdlpSelectedEpisodes(ytdlpData.episodes!.map((e: SmartEpisode) => e.id))
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
                      onClick={() => setYtdlpSelectedEpisodes([])}
                    >
                      Odznači sve
                    </button>
                  </div>
                </div>
                <div className="smart-ep-list">
                  {ytdlpData.episodes.map((ep: SmartEpisode, idx: number) => {
                    const checked = ytdlpSelectedEpisodes.includes(ep.id);
                    return (
                      <div
                        key={ep.id ?? idx}
                        className={`smart-ep-item ${checked ? "selected" : ""}`}
                        onClick={() =>
                          setYtdlpSelectedEpisodes(
                            checked
                              ? ytdlpSelectedEpisodes.filter((id) => id !== ep.id)
                              : [...ytdlpSelectedEpisodes, ep.id],
                          )
                        }
                        style={
                          checked
                            ? { borderLeft: `3px solid ${THEME.color}80` }
                            : { borderLeft: "3px solid transparent" }
                        }
                      >
                        <div
                          className={`custom-checkbox-box ${checked ? "checked" : ""}`}
                          style={
                            checked
                              ? { background: THEME.color, borderColor: THEME.color }
                              : {}
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
                              color: THEME.color,
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
                          <span
                            style={{ fontSize: "0.7rem", color: "var(--text-muted)", flexShrink: 0 }}
                          >
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
            )}

            <YtdlpDownloadPanel
              data={ytdlpData}
              resolution={ytdlpResolution}
              setResolution={setYtdlpResolution}
              subs={ytdlpSubs}
              setSubs={setYtdlpSubs}
              audioOnly={ytdlpAudioOnly}
              setAudioOnly={setYtdlpAudioOnly}
              useAria2={ytdlpUseAria2}
              setUseAria2={setYtdlpUseAria2}
              ytdlpCookiesBrowser={ytdlpCookiesBrowser}
              setYtdlpCookiesBrowser={setYtdlpCookiesBrowser}
              ytdlpImpersonate={ytdlpImpersonate}
              setYtdlpImpersonate={setYtdlpImpersonate}
              ytdlpProxy={ytdlpProxy}
              setYtdlpProxy={setYtdlpProxy}
              ytdlpGeoBypass={ytdlpGeoBypass}
              setYtdlpGeoBypass={setYtdlpGeoBypass}
              ytdlpEmbedThumbnail={ytdlpEmbedThumbnail}
              setYtdlpEmbedThumbnail={setYtdlpEmbedThumbnail}
              ytdlpEmbedMetadata={ytdlpEmbedMetadata}
              setYtdlpEmbedMetadata={setYtdlpEmbedMetadata}
              ytdlpLimitRate={ytdlpLimitRate}
              setYtdlpLimitRate={setYtdlpLimitRate}
              ytdlpHardsub={ytdlpHardsub}
              setYtdlpHardsub={setYtdlpHardsub}
              ytdlpSponsorblockMode={ytdlpSponsorblockMode}
              setYtdlpSponsorblockMode={setYtdlpSponsorblockMode}
              ytdlpSplitChapters={ytdlpSplitChapters}
              setYtdlpSplitChapters={setYtdlpSplitChapters}
              ytdlpDownloadPlaylist={ytdlpDownloadPlaylist}
              setYtdlpDownloadPlaylist={setYtdlpDownloadPlaylist}
              ytdlpPlaylistItems={ytdlpPlaylistItems}
              setYtdlpPlaylistItems={setYtdlpPlaylistItems}
              ytdlpFormatSpec={ytdlpFormatSpec}
              setYtdlpFormatSpec={setYtdlpFormatSpec}
              ytdlpExtractorArgs={ytdlpExtractorArgs}
              setYtdlpExtractorArgs={setYtdlpExtractorArgs}
              ytdlpCookiesConfigured={ytdlpCookiesConfigured}
              ytdlpCookiesUploading={ytdlpCookiesUploading}
              uploadYtdlpCookies={uploadYtdlpCookies}
              clearYtdlpCookies={clearYtdlpCookies}
              subsOpen={subsOpen}
              setSubsOpen={setSubsOpen}
              hardsubInputId="ytdlpHardsub-universal"
            />

            <button
              type="button"
              className="smart-cta-btn smart-cta-ytdlp w-full mt-4"
              onClick={() => void startYtdlpDownload()}
              disabled={
                ytdlpSubmitting ||
                !ytdlpData.target_id ||
                (ytdlpData.episodes &&
                  ytdlpData.episodes.length > 0 &&
                  ytdlpSelectedEpisodes.length === 0)
              }
            >
              {ytdlpSubmitting ? (
                <Loader2 style={{ width: 18, height: 18, animation: "spin 1s linear infinite" }} />
              ) : (
                <Download style={{ width: 18, height: 18 }} />
              )}
              {ytdlpSubmitting ? "Dodavanje u red..." : "Dodaj u red preuzimanja"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
