import {
  Copy,
  Download,
  Globe,
  Loader2,
  Search,
  X,
  Zap,
} from "lucide-react";
import { useAppShellSlice } from "../../context/appStore";
import { buildYtdlpCtaLabel } from "../../hooks/domains/ytdlpShared";
import { useYtdlpTab } from "../../hooks/domains/useYtdlpTab";
import { YtdlpDownloadPanel } from "../ytdlp/YtdlpDownloadPanel";
import { YtdlpPreviewPanel } from "../ytdlp/YtdlpPreviewPanel";
import { YtdlpSidebar } from "../ytdlp/YtdlpSidebar";
import { YTDLP_PLATFORM_EXAMPLES } from "../ytdlp/ytdlpTheme";
import { cssVars } from "../../utils/cssVars";

export function UniversalTab() {
  const { showToast } = useAppShellSlice();
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

  const ctaDisabled =
    ytdlpSubmitting ||
    !ytdlpData?.target_id ||
    (!!ytdlpData?.episodes?.length && ytdlpSelectedEpisodes.length === 0);

  const ctaLabel = buildYtdlpCtaLabel({
    submitting: ytdlpSubmitting,
    mode: ytdlpData?.mode,
    selectedCount: ytdlpSelectedEpisodes.length,
    totalEpisodes: ytdlpData?.episodes?.length,
  });

  const handlePaste = async () => {
    try {
      const text = await navigator.clipboard.readText();
      if (text.trim().startsWith("http")) {
        setYtdlpUrl(text.trim());
        void analyzeYtdlpUrl(text.trim());
        showToast("Link uspešno zalepljen!", "success");
      } else {
        showToast("Clipboard ne sadrži validan URL.", "error");
      }
    } catch {
      showToast("Dozvola za clipboard nije odobrena.", "error");
    }
  };

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

      <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
        <div className="md:col-span-2 flex flex-col gap-6">
          <div className="glass-panel p-6 md:p-8 rounded-xl border border-glass flex flex-col gap-6 glow-blue-card glow-card-premium">
            <div>
              <label>URL videa ili plejliste</label>
              <div className="smart-url-wrap">
                <Globe className="smart-url-input-icon w-4 h-4" />
                <input
                  type="text"
                  placeholder="Nalepite link — analiza počinje automatski"
                  value={ytdlpUrl}
                  onChange={(e) => {
                    setYtdlpUrl(e.target.value);
                    debouncedAnalyze(e.target.value);
                  }}
                  onKeyDown={(e) => e.key === "Enter" && analyzeYtdlpUrl(ytdlpUrl)}
                  className="smart-url-input"
                  style={cssVars({
                    "--focused-border": "#3b82f6",
                    "--focused-glow": "rgba(59,130,246,0.25)",
                  })}
                />
                <button
                  type="button"
                  className="smart-url-paste-btn"
                  title="Nalepi iz clipboard-a"
                  onClick={() => void handlePaste()}
                >
                  <Copy style={{ width: 14, height: 14 }} />
                </button>
                <button
                  type="button"
                  className="ytdlp-url-analyze-btn"
                  onClick={() => analyzeYtdlpUrl(ytdlpUrl)}
                  disabled={ytdlpLoading || ytdlpSubmitting || !ytdlpUrl.trim()}
                >
                  {ytdlpLoading ? (
                    <Loader2 size={16} className="animate-spin" />
                  ) : (
                    <Search size={16} />
                  )}
                  {ytdlpLoading ? "Analizira..." : "Analiziraj"}
                </button>
              </div>
              {ytdlpData && (
                <button
                  type="button"
                  className="text-[10px] font-extrabold uppercase text-text-muted hover:text-white px-3 py-2 rounded border border-white/10 mt-2"
                  onClick={cancelYtdlpPreview}
                >
                  <X className="w-3 h-3 inline mr-1" />
                  Poništi preview
                </button>
              )}
            </div>

            <div className="flex flex-wrap gap-2">
              <span className="text-[10px] text-text-muted font-bold self-center mr-1">PRIMERI:</span>
              {YTDLP_PLATFORM_EXAMPLES.map((p) => (
                <button
                  key={p.label}
                  type="button"
                  className="smart-platform-pill text-blue-400 border border-blue-500/20 hover:border-blue-500/40 transition-colors cursor-pointer"
                  style={{ background: "rgba(59,130,246,0.08)" }}
                  title={`Učitaj primer: ${p.label}`}
                  onClick={() => {
                    setYtdlpUrl(p.url);
                    void analyzeYtdlpUrl(p.url);
                  }}
                >
                  {p.label}
                </button>
              ))}
            </div>
          </div>

          <YtdlpPreviewPanel
            data={ytdlpData}
            loading={ytdlpLoading}
            selectedEpisodes={ytdlpSelectedEpisodes}
            setSelectedEpisodes={setYtdlpSelectedEpisodes}
            subs={ytdlpSubs}
            setSubs={setYtdlpSubs}
          >
            {ytdlpData && (
              <>
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
                  disabled={ctaDisabled}
                >
                  {ytdlpSubmitting ? (
                    <Loader2 style={{ width: 18, height: 18, animation: "spin 1s linear infinite" }} />
                  ) : (
                    <Download style={{ width: 18, height: 18 }} />
                  )}
                  {ctaLabel}
                </button>
              </>
            )}
          </YtdlpPreviewPanel>
        </div>

        <YtdlpSidebar status={status} cookiesConfigured={ytdlpCookiesConfigured} />
      </div>
    </div>
  );
}
