import { useEffect, useState } from "react";
import {
  Check,
  Copy,
  Download,
  Globe,
  Info,
  Loader2,
  Lock,
  Search,
  Zap,
} from "lucide-react";
import { CustomSelect } from "../CustomSelect";
import { YtdlpDownloadPanel } from "../ytdlp/YtdlpDownloadPanel";
import { YtdlpEpisodeList } from "../ytdlp/YtdlpEpisodeList";
import { YtdlpPreviewExtras } from "../ytdlp/YtdlpPreviewHeader";
import { buildYtdlpCtaLabel } from "../../hooks/domains/ytdlpShared";
import { VoyoSeasonList } from "../voyo/VoyoSeasonList";
import {
  selectableSmartEpisodeIds,
  VOYO_HINT_MSG,
  voyoCatalogDrmHint,
  voyoIsHardBlocked,
  voyoIsSoftHint,
} from "../../lib/voyoDrm";
import type { ServiceStatus, SmartEpisode, VoyoEpisode } from "../../types/app";
import { useSmartDashboardTab } from "../../hooks/domains/useSmartDashboardTab";
import { cssVars } from "../../utils/cssVars";

export function DashboardTab() {
  const {
    debouncedDetect,
    handleSmartDetect,
    setSmartAudioOnly,
    setSmartData,
    setSmartEpisodesRange,
    setSmartResolution,
    setSmartRtsVerbose,
    setSmartSelectedEpisodes,
    setSmartSubs,
    setSmartUrl,
    setSmartUseAria2,
    showToast,
    smartAudioOnly,
    smartData,
    smartEpisodesRange,
    smartLoading,
    smartResolution,
    smartRtsVerbose,
    smartSelectedEpisodes,
    smartSubs,
    smartUrl,
    smartUseAria2,
    smartSubmitting,
    smartRtsStartEp,
    setSmartRtsStartEp,
    smartRtsEndEp,
    setSmartRtsEndEp,
    startSmartDownload,
    status,
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
    smartSkyVcodec,
    setSmartSkyVcodec,
    smartSkyQuality,
    setSmartSkyQuality,
    smartSkyAudioLang,
    setSmartSkyAudioLang,
    smartHboAudio,
    setSmartHboAudio,
  } = useSmartDashboardTab();

  const [subsOpen, setSubsOpen] = useState(true);
// Service theme config
  const SVC_THEMES: Record<string, {emoji:string; name:string; color:string; glow:string; example:string; exampleLabel:string}> = {
    voyo:    { emoji:"🟠", name:"Voyo",        color:"#f97316", glow:"rgba(249,115,22,0.08)",   example:"https://voyo.rs/film_50584.html", exampleLabel:"voyo.rs / voyo.hr" },
    hrti:    { emoji:"🔵", name:"HRTi",        color:"#06b6d4", glow:"rgba(6,182,212,0.08)",    example:"https://hrti.hrt.hr/video/show/4a3b2c1d-0000-0000-0000-000000000001", exampleLabel:"Video (UUID)" },
    eon:     { emoji:"🟢", name:"EON TV",      color:"#10b981", glow:"rgba(16,185,129,0.08)",   example:"https://eon.tv/player/vod-abc123", exampleLabel:"VOD naslov" },
    rts:     { emoji:"🔴", name:"RTS Planeta", color:"#f43f5e", glow:"rgba(244,63,94,0.08)",    example:"https://www.rtsplaneta.rs/video/show/12345", exampleLabel:"Epizoda/emisija" },
    rtsplaneta: { emoji:"🔴", name:"RTS Planeta", color:"#f43f5e", glow:"rgba(244,63,94,0.08)", example:"https://www.rtsplaneta.rs/video/show/12345", exampleLabel:"Epizoda/emisija" },
    hbomax:  { emoji:"🟣", name:"HBO Max",     color:"#9333ea", glow:"rgba(147,51,234,0.08)",   example:"https://www.max.com/show/urn:hbo:episode:xyz123", exampleLabel:"Epizoda/film" },
    skyshowtime: { emoji:"🩵", name:"SkyShowtime", color:"#14b8a6", glow:"rgba(20,184,166,0.08)", example:"https://www.skyshowtime.com/watch/asset/tv/naziv/ID", exampleLabel:"Serija ili film" },
    ytdlp:   { emoji:"🌐", name:"Univerzalno",  color:"#3b82f6", glow:"rgba(59,130,246,0.08)",   example:"https://www.youtube.com/watch?v=dQw4w9WgXcQ", exampleLabel:"YouTube, X, TikTok, FB..." },
  };
  const svcKeys = Object.keys(SVC_THEMES).filter(k => k !== "rtsplaneta");

  useEffect(() => {
    if (smartData?.service === "ytdlp") {
      setSubsOpen(true);
    }
  }, [smartData?.service, smartData?.target_id]);
  // Service auth sub-text (from status if available)
  const getSvcStatus = (k: string) => {
    if (k === "ytdlp") {
      const ytdlp = status?.services?.ytdlp;
      const ready = ytdlp?.ready ?? ytdlp?.authenticated ?? true;
      const ver = (ytdlp as { ytdlp_version?: string } | undefined)?.ytdlp_version;
      return {
        online: !!ready,
        label: ready ? (ver ? `yt-dlp ${ver}` : "Uvek aktivno") : (ytdlp?.error || "Nedostaje Node.js"),
      };
    }
    const s = status?.services;
    if (!s) return { online: false, label: "Nije podešeno" };
    const svc = s[k === "rts" ? "rtsplaneta" : k] as ServiceStatus | undefined;
    if (!svc) return { online: false, label: "Nije podešeno" };
    const authenticated = svc.authenticated || svc.ready;
    const email = svc.email || svc.username || svc.nickname || "";
    return { online: !!authenticated, label: email ? email : (authenticated ? "Aktivan" : "Nije podešeno") };
  };
  // Preview panel service theme
  const previewTheme = smartData ? SVC_THEMES[smartData.service] ?? SVC_THEMES.voyo : null;
  const ignoreCatalogDrmHint = status?.voyo_ignore_catalog_drm_hint === true;

  return (
  <div key="dashboard" className="tab-content tab-content-dash max-w-5xl mx-auto flex flex-col gap-5">
    {/* Tab header */}
    <div className="tab-page-header tab-header-dash" style={{ padding: "12px 18px", marginBottom: "0px", borderRadius: "14px" }}>
      <div className="tab-page-header-icon" style={{ background: "linear-gradient(135deg,#f59e0b,#d97706)", width: 36, height: 36, borderRadius: 8 }}>
        <Zap style={{ width: 18, height: 18, color: "white" }} />
      </div>
      <div style={{ flex: 1 }}>
        <h2 className="text-lg font-extrabold text-white mb-0.5 flex items-center gap-2">
          <Zap className="w-4 h-4 text-amber-400" /> Pametno Preuzimanje
        </h2>
        <p className="text-text-secondary text-xs">Automatsko prepoznavanje i preuzimanje videa sa svih podržanih platformi.</p>
      </div>
    </div>

    {/* ── Sleek Compact Platform Status Row (Interactive Pills) ── */}
    <div className="smart-svc-bar my-0.5">
      {svcKeys.map(k => {
        const t = SVC_THEMES[k];
        const st = getSvcStatus(k);
        return (
          <div
            key={k}
            className="smart-svc-pill group"
            style={cssVars({ 
              "--svc-glow": t.glow, 
              "--svc-glow-hover": t.glow.replace("0.08", "0.25"), 
              "--svc-color": t.color, 
              borderColor: st.online ? `${t.color}35` : "rgba(255,255,255,0.04)",
              background: st.online ? `${t.color}0c` : "rgba(255,255,255,0.015)"
            })}
            onClick={() => { setSmartUrl(t.example); handleSmartDetect(t.example); }}
            title={`Klikni da učitaš primer za ${t.name}`}
          >
            <span className="smart-svc-pill-emoji">{t.emoji}</span>
            <span className="smart-svc-pill-name">{t.name}</span>
            <span className="flex items-center gap-1.5 border-l border-white/[0.08] pl-2">
              <span className={`smart-svc-pill-dot ${st.online ? "online" : "offline"}`} />
              <span className={`smart-svc-pill-status ${st.online ? "text-emerald-400" : "text-text-muted"}`}>
                {st.online ? st.label : "Nije podešeno"}
              </span>
            </span>
          </div>
        );
      })}
    </div>
    
    {/* System Metrics Grid removed from here - relocated to the bottom */}

    {/* ── Smart Console Card Wrapper ── */}
    <div className="smart-console-card">
      <div className="console-scanline" />
      
      <div className="flex items-center gap-2.5 mb-4 border-b border-white/[0.04] pb-3">
        <Globe className="w-4.5 h-4.5 text-amber-500 animate-spin" style={{ animationDuration: "10s" }} />
        <div>
          <h3 className="font-extrabold text-sm text-white tracking-wide uppercase">Pametni Media Skener</h3>
          <p className="text-text-secondary text-[11px]">Unesite link za automatsku ekstrakciju formata, epizoda i DRM detalja</p>
        </div>
      </div>

      <div className="flex flex-col gap-4">
        {/* ── URL Input Bar ── */}
        <div className="smart-url-wrap">
          <Globe className="smart-url-input-icon w-4 h-4" />
          <input
            type="text"
            className="smart-url-input"
            placeholder="npr. https://voyo.rs/uspeh-1_50584.html, hrti.hrt.hr, rtsplaneta.rs, eon.tv, max.com..."
            value={smartUrl}
            onChange={e => {
              setSmartUrl(e.target.value);
              if (e.target.value.trim().startsWith("http")) debouncedDetect(e.target.value);
            }}
            onKeyDown={e => e.key === "Enter" && handleSmartDetect(smartUrl)}
          />
          {/* Clipboard paste btn */}
          <button
            className="smart-url-paste-btn"
            title="Nalepi iz clipboard-a"
            onClick={async () => {
              try {
                const text = await navigator.clipboard.readText();
                if (text.trim().startsWith("http")) { 
                  setSmartUrl(text.trim()); 
                  handleSmartDetect(text.trim()); 
                  showToast("Link uspešno zalepljen!", "success");
                }
                else showToast("Clipboard ne sadrži validan URL.", "error");
              } catch { showToast("Dozvola za clipboard nije odobrena.", "error"); }
            }}
          >
            <Copy style={{width:14,height:14}} />
          </button>
          <button
            className="smart-url-analyze-btn"
            onClick={() => handleSmartDetect(smartUrl)}
            disabled={smartLoading || smartSubmitting || !smartUrl}
          >
            {smartLoading ? <Loader2 style={{width:16,height:16,animation:"spin 1s linear infinite"}} /> : <Search style={{width:16,height:16}} />}
            {smartLoading ? "Analizira..." : "Analiziraj"}
          </button>
        </div>

        {/* Platform Pills */}
        <div className="smart-supported-platforms">
          <span className="text-[10px] text-text-muted font-bold self-center mr-2">PODRŽANO:</span>
          <span className="smart-platform-pill">Voyo.rs Film/Serije</span>
          <span className="smart-platform-pill">HRTi Katalog</span>
          <span className="smart-platform-pill">EON VOD & Uživo</span>
          <span className="smart-platform-pill">RTS Planeta</span>
          <span className="smart-platform-pill">HBO Max</span>
          <span className="smart-platform-pill text-blue-400 border border-blue-500/20" style={{background:"rgba(59,130,246,0.08)"}}>YouTube / X / FB / TikTok / Vimeo / ostali...</span>
        </div>
      </div>
    </div>

    <div className="flex flex-col gap-5 w-full">

      {/* ── Loading skeleton while analyzing ── */}
      {smartLoading && !smartData && (
        <div className="smart-preview-panel" style={{borderColor:"rgba(255,255,255,0.08)", padding:"32px", display:"flex", flexDirection:"column", alignItems:"center", gap:"16px"}}>
          <Loader2 style={{width:32,height:32,color:"#f59e0b",animation:"spin 1s linear infinite"}} />
          <p className="text-sm font-bold text-white">Analiziramo vaš link...</p>
          <p className="text-xs text-text-muted">Prepoznavanje servisa, ekstrakcija metapodataka i dostupnih formata</p>
        </div>
      )}

      {/* ── Preview & Download Panel ── */}
      {smartData && previewTheme && (
        <div
          className="smart-preview-panel"
          style={{
            borderColor: `${previewTheme.color}40`,
            boxShadow: `0 0 40px ${previewTheme.glow}, 0 4px 24px rgba(0,0,0,0.4)`,
          }}
        >
          {/* Header */}
          <div className="smart-preview-header" style={{borderBottom:"1px solid rgba(255,255,255,0.05)", paddingBottom:20}}>
            <div className="smart-preview-thumb" style={{borderColor:`${previewTheme.color}30`}}>
              {smartData.thumbnail
                ? <img src={smartData.thumbnail} alt={smartData.title} />
                : <span style={{fontSize:"2rem"}}>{previewTheme.emoji}</span>
              }
            </div>
            <div style={{flex:1}}>
              <div
                className="smart-preview-badge"
                style={{background:`${previewTheme.color}18`, color:previewTheme.color, border:`1px solid ${previewTheme.color}35`}}
              >
                {previewTheme.emoji} {previewTheme.name} · {smartData.mode?.toUpperCase()}
              </div>
              <h3 className="smart-preview-title">{smartData.title}</h3>
              {smartData.service !== "ytdlp" && smartData.generic_url && !smartData.metadata_partial && (
                <div className="mt-2 px-3 py-2 rounded-lg border border-blue-500/25 bg-blue-500/10 text-[11px] font-bold text-blue-300">
                  Link nije prepoznat kao poznati servis — koristi se univerzalni yt-dlp preuzimač.
                </div>
              )}
              {smartData.service !== "ytdlp" && smartData.metadata_partial && (
                <div className="mt-2 px-3 py-2 rounded-lg border border-amber-500/30 bg-amber-500/10 text-[11px] font-bold text-amber-300">
                  Metapodaci nisu u potpunosti dostupni — preuzimanje je i dalje moguće. Proverite da li je Node.js instaliran.
                </div>
              )}
              {smartData.service === "voyo" && smartData.mode === "video" && voyoIsHardBlocked(smartData) && (
                <div className="mt-2 px-3 py-2 rounded-lg border border-red-500/35 bg-red-500/10 text-[11px] font-bold text-red-300 flex items-center gap-2">
                  <Lock style={{ width: 12, height: 12, flexShrink: 0 }} />
                  {smartData.stream_reason || "Stream nije dostupan za preuzimanje."}
                </div>
              )}
              {smartData.service === "voyo" && smartData.mode === "video" && voyoIsSoftHint(smartData, ignoreCatalogDrmHint) && (
                <div className="mt-2 px-3 py-2 rounded-lg border border-amber-500/35 bg-amber-500/10 text-[11px] font-bold text-amber-300 flex items-center gap-2">
                  <Lock style={{ width: 12, height: 12, flexShrink: 0 }} />
                  {VOYO_HINT_MSG}
                </div>
              )}
              {smartData.service === "voyo" && smartData.mode === "video" && smartData.probe_ok && smartData.streamable && voyoCatalogDrmHint(smartData) && (
                <div className="mt-2 px-3 py-2 rounded-lg border border-emerald-500/30 bg-emerald-500/10 text-[11px] font-bold text-emerald-300">
                  Stream je dostupan (AES-128 HLS).
                </div>
              )}
              {smartData.description && <p className="smart-preview-desc">{smartData.description}</p>}
              {smartData.service === "ytdlp" && (
                <YtdlpPreviewExtras
                  data={smartData}
                  subs={smartSubs}
                  setSubs={setSmartSubs}
                  theme={{ color: previewTheme.color, glow: previewTheme.glow, emoji: previewTheme.emoji, name: previewTheme.name }}
                />
              )}
            </div>
          </div>

          {/* Body */}
          <div className="smart-preview-body">
            {/* Episode checklist (series with episodes) */}
            {smartData.service === "voyo" && smartData.seasons && smartData.seasons.length > 0 && smartData.episodes && (
              <VoyoSeasonList
                showHeader={false}
                voyoSeriesData={{
                  title: smartData.title,
                  description: smartData.description || "",
                  seasons: smartData.seasons,
                  episodes: smartData.episodes as VoyoEpisode[],
                }}
                selectedVoyoEpisodes={smartSelectedEpisodes.map((id) => Number(id))}
                setSelectedVoyoEpisodes={(ids) => setSmartSelectedEpisodes(ids)}
                ignoreCatalogDrmHint={ignoreCatalogDrmHint}
              />
            )}

            {smartData.service === "ytdlp" && smartData.episodes && smartData.episodes.length > 0 && (
              <YtdlpEpisodeList
                data={smartData}
                selectedEpisodes={smartSelectedEpisodes}
                setSelectedEpisodes={setSmartSelectedEpisodes}
                theme={{ color: previewTheme.color, glow: previewTheme.glow, emoji: previewTheme.emoji, name: previewTheme.name }}
              />
            )}

            {smartData.episodes && smartData.episodes.length > 0 && smartData.service !== "ytdlp" && !(smartData.service === "voyo" && smartData.seasons?.length) && (
              <div>
                <div style={{display:"flex", justifyContent:"space-between", alignItems:"center", marginBottom:10}}>
                  <label style={{margin:0}}>
                    {`Epizode (${smartSelectedEpisodes.length}/${smartData.episodes.length} odabrano)`}
                  </label>
                  <div style={{display:"flex", gap:12}}>
                    <button
                      style={{fontSize:"0.72rem", fontWeight:700, color:previewTheme.color, background:"none", border:"none", cursor:"pointer"}}
                      onClick={() => setSmartSelectedEpisodes(
                        smartData.service === "voyo"
                          ? selectableSmartEpisodeIds(smartData.episodes!)
                          : smartData.episodes!.map((e: SmartEpisode) => e.id),
                      )}
                    >Označi sve</button>
                    <span style={{color:"var(--text-muted)"}}>|</span>
                    <button
                      style={{fontSize:"0.72rem", fontWeight:700, color:"var(--text-muted)", background:"none", border:"none", cursor:"pointer"}}
                      onClick={() => setSmartSelectedEpisodes([])}
                    >Odznači sve</button>
                  </div>
                </div>
                <div className="smart-ep-list">
                  {smartData.episodes.map((ep: SmartEpisode, idx: number) => {
                    const blocked = smartData.service === "voyo" && voyoIsHardBlocked(ep);
                    const softHint = smartData.service === "voyo" && voyoIsSoftHint(ep, ignoreCatalogDrmHint);
                    const checked = !blocked && smartSelectedEpisodes.includes(ep.id);
                    return (
                      <div
                        key={ep.id ?? idx}
                        className={`smart-ep-item ${checked ? "selected" : ""} ${blocked ? "opacity-45 cursor-not-allowed" : softHint ? "opacity-90" : ""}`}
                        onClick={() => {
                          if (blocked) return;
                          setSmartSelectedEpisodes(checked
                            ? smartSelectedEpisodes.filter((id: number | string) => id !== ep.id)
                            : [...smartSelectedEpisodes, ep.id],
                          );
                        }}
                        title={
                          blocked
                            ? ep.stream_reason || "Stream nije dostupan"
                            : softHint
                              ? "Katalog DRM hint — možete probati preuzimanje"
                              : undefined
                        }
                        style={checked ? {borderLeft:`3px solid ${previewTheme.color}80`} : {borderLeft:"3px solid transparent"}}
                      >
                        <div className={`custom-checkbox-box ${checked ? "checked" : ""}`} style={checked ? {background:previewTheme.color, borderColor:previewTheme.color} : {}}>
                          <svg className="custom-checkbox-check" viewBox="0 0 10 10" fill="none" stroke="white" strokeWidth="2">
                            <polyline points="1.5 5 4 7.5 8.5 2" />
                          </svg>
                        </div>
                        {(ep.season && ep.episode) && (
                          <span style={{fontSize:"0.72rem", fontWeight:800, color:previewTheme.color, minWidth:52, flexShrink:0}}>
                            S{String(ep.season).padStart(2,"0")}E{String(ep.episode).padStart(2,"0")}
                          </span>
                        )}
                        <span style={{flex:1, fontSize:"0.82rem", color:"white", overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap"}}>
                          {ep.title}
                        </span>
                        {(ep.length_mins ?? 0) > 0 && <span style={{fontSize:"0.7rem", color:"var(--text-muted)", flexShrink:0}}>{ep.length_mins}m</span>}
                        {blocked && <Lock style={{width:12,height:12,color:"#f87171",flexShrink:0}} />}
                        {!blocked && softHint && <Lock style={{width:12,height:12,color:"#f59e0b",flexShrink:0}} />}
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* Config row */}
            {smartData.service === "ytdlp" ? (
                <YtdlpDownloadPanel
                  data={smartData}
                  resolution={smartResolution}
                  setResolution={setSmartResolution}
                  subs={smartSubs}
                  setSubs={setSmartSubs}
                  audioOnly={smartAudioOnly}
                  setAudioOnly={setSmartAudioOnly}
                  useAria2={smartUseAria2}
                  setUseAria2={setSmartUseAria2}
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
                  hardsubInputId="ytdlpHardsub-dashboard"
                />
            ) : (
              <div className="smart-config-row">
                <>
                  {smartData.service === "hbomax" && (
                    <div>
                      <label>Audio trake</label>
                      <CustomSelect
                        value={smartHboAudio}
                        options={["all", "first"]}
                        onChange={(val) => setSmartHboAudio(val)}
                        formatLabel={(val) =>
                          val === "all" ? "Svi jezici (preporučeno)" : "Samo primarni (en/und)"
                        }
                      />
                    </div>
                  )}
                  {smartData.service === "skyshowtime" && (
                    <>
                      <div>
                        <label>Video kodek</label>
                        <CustomSelect
                          value={smartSkyVcodec}
                          options={["H264", "H265"]}
                          onChange={(val) => setSmartSkyVcodec(val)}
                          formatLabel={(val) => val === "H264" ? "H.264" : "H.265 (HEVC)"}
                        />
                      </div>
                      <div>
                        <label>Kvalitet</label>
                        <CustomSelect
                          value={smartSkyQuality}
                          options={["SDR", "HDR10", "DV"]}
                          onChange={(val) => setSmartSkyQuality(val)}
                          formatLabel={(val) => val}
                        />
                      </div>
                      <div>
                        <label>Audio jezik</label>
                        <CustomSelect
                          value={smartSkyAudioLang}
                          options={["en", "sr", "hr", "sl"]}
                          onChange={(val) => setSmartSkyAudioLang(val)}
                          formatLabel={(val) => val.toUpperCase()}
                        />
                      </div>
                    </>
                  )}
                  {smartData.service === "voyo" && (
                    <div>
                      <label>Maks. rezolucija</label>
                      <CustomSelect
                        value={smartResolution}
                        options={["2160p (4K)", "1080p (Full HD)", "720p (HD)", "480p (SD)"]}
                        onChange={(val) => setSmartResolution(val)}
                      />
                      <p style={{fontSize:"0.68rem",color:"var(--text-muted)",marginTop:4}}>Najbolji stream do izabrane visine.</p>
                    </div>
                  )}
                  {smartData.service === "hbomax" && (
                    <div>
                      <label>Titlovi</label>
                      <input
                        type="text"
                        value={smartSubs}
                        onChange={e => setSmartSubs(e.target.value)}
                        placeholder="all ili sr,hr,en — none za bez titlova"
                        className="py-2.5 px-3 bg-black/40 border border-glass text-white rounded focus:outline-none w-full"
                      />
                    </div>
                  )}
                  {(smartData.mode === "series" && !smartData.episodes) && (
                    <div>
                      <label>Raspon epizoda (opciono)</label>
                      <input type="text" value={smartEpisodesRange} onChange={e=>setSmartEpisodesRange(e.target.value)}
                        placeholder="npr. 1-3 ili 2-"
                        className="py-2.5 px-3 bg-black/40 border border-glass text-white rounded focus:outline-none w-full" />
                      <p style={{fontSize:"0.68rem",color:"var(--text-muted)",marginTop:4}}>Ostavite prazno za sve epizode.</p>
                    </div>
                  )}
                  {["rts", "rtsplaneta"].includes(smartData.service) && (
                    <div className="flex flex-col gap-3" style={{marginTop: 16}}>
                      <div className="flex gap-3 items-end">
                        <div style={{flex:1}}>
                          <label>Početna epizoda</label>
                          <input type="number" min="1" value={smartRtsStartEp} onChange={e => setSmartRtsStartEp(e.target.value)}
                            placeholder="npr. 1"
                            className="py-2.5 px-3 bg-black/40 border border-glass text-white rounded focus:outline-none w-full" />
                        </div>
                        <div style={{flex:1}}>
                          <label>Krajnja epizoda</label>
                          <input type="number" min="1" value={smartRtsEndEp} onChange={e => setSmartRtsEndEp(e.target.value)}
                            placeholder="npr. 10"
                            className="py-2.5 px-3 bg-black/40 border border-glass text-white rounded focus:outline-none w-full" />
                        </div>
                      </div>
                      <p style={{fontSize:"0.68rem",color:"var(--text-muted)",marginTop:-4}}>Ostavite prazno za sve epizode ili jedan video.</p>
                      <label className="custom-checkbox-wrap" style={{cursor: "pointer"}}>
                        <input
                          type="checkbox"
                          checked={smartRtsVerbose}
                          onChange={e => setSmartRtsVerbose(e.target.checked)}
                        />
                        <div className={`custom-checkbox-box ${smartRtsVerbose ? "checked" : ""}`} style={smartRtsVerbose ? {background:"#f43f5e", borderColor:"#f43f5e"} : {}}>
                          <svg className="custom-checkbox-check" viewBox="0 0 10 10" fill="none" stroke="white" strokeWidth="2">
                            <polyline points="1.5 5 4 7.5 8.5 2" />
                          </svg>
                        </div>
                        <span className="text-sm font-semibold text-white">Verbose/Detaljan Log preuzimanja</span>
                      </label>
                    </div>
                  )}
                </>
              </div>
            )}

            {/* CTA */}
            <div style={{display:"flex", alignItems:"center", gap:14}}>
              <button
                className={`smart-cta-btn smart-cta-${smartData.service}`}
                onClick={startSmartDownload}
                disabled={
                  smartSubmitting
                  || (smartData.episodes && smartSelectedEpisodes.length === 0)
                  || (smartData.service === "voyo" && smartData.mode === "video" && voyoIsHardBlocked(smartData))
                }
              >
                {smartSubmitting
                  ? <Loader2 style={{width:18,height:18,animation:"spin 1s linear infinite"}} />
                  : <Download style={{width:18,height:18}} />
                }
                {smartData.service === "ytdlp"
                  ? buildYtdlpCtaLabel({
                      submitting: smartSubmitting,
                      mode: smartData.mode,
                      selectedCount: smartSelectedEpisodes.length,
                      totalEpisodes: smartData.episodes?.length,
                    })
                  : smartSubmitting
                    ? "Slanje..."
                    : smartData.episodes
                      ? `Preuzmi ${smartSelectedEpisodes.length} epizod${smartSelectedEpisodes.length === 1 ? "u" : smartSelectedEpisodes.length < 5 ? "e" : "a"}`
                      : "Pokreni Preuzimanje"
                }
              </button>
              <button
                onClick={() => {
                  setSmartData(null);
                  setSmartUrl("");
                  setSmartSelectedEpisodes([]);
                  setSmartEpisodesRange("");
                  setSmartRtsStartEp("");
                  setSmartRtsEndEp("");
                  setYtdlpCookiesBrowser("");
                  setYtdlpImpersonate(false);
                  setYtdlpProxy("");
                  setYtdlpGeoBypass(false);
                  setYtdlpEmbedThumbnail(false);
                  setYtdlpEmbedMetadata(false);
                  setYtdlpLimitRate("");
                  setYtdlpSponsorblockMode("remove");
                  setYtdlpSplitChapters(false);
                  setYtdlpDownloadPlaylist(false);
                  setYtdlpPlaylistItems("");
                  setYtdlpHardsub(false);
                  setSmartAudioOnly(false);
                  setSmartUseAria2(false);
                  setSubsOpen(true);
                }}
                disabled={smartSubmitting}
                style={{fontSize:"0.75rem", color:"var(--text-muted)", background:"none", border:"none", cursor: smartSubmitting ? "not-allowed" : "pointer", opacity: smartSubmitting ? 0.4 : 1}}
              >✕ Otkaži</button>
            </div>
          </div>
        </div>
      )}
    </div>

    {/* ── Platform Capabilities Info Console ── */}
    <div className="mt-2 w-full flex flex-col gap-3">
      <div className="flex items-center gap-2 border-b border-white/[0.04] pb-2.5">
        <Info className="w-4 h-4 text-indigo-400" />
        <h3 className="font-extrabold text-[11px] text-white tracking-widest uppercase">Mogućnosti i Status Platformi</h3>
      </div>
      
      <div className="smart-info-grid">
        
        {/* Voyo Card */}
        <div className="smart-info-card" style={cssVars({ "--card-brand-color": "#f97316" })}>
          <div className="smart-info-card-title-wrap">
            <div className="smart-info-card-title">
              <span>🟠</span> Voyo
            </div>
            <div className="smart-info-card-badge text-orange-400 border-orange-500/20">
              1080p · DRM
            </div>
          </div>
          <div className="smart-info-card-features">
            <div className="smart-info-card-feature">
              <Check className="w-3.5 h-3.5" /> <span>Filmovi, Serije & Epizode</span>
            </div>
            <div className="smart-info-card-feature">
              <Check className="w-3.5 h-3.5" /> <span>Automatsko preuzimanje titlova</span>
            </div>
            <div className="smart-info-card-feature">
              <Check className="w-3.5 h-3.5" /> <span>Widevine L3 Auto-Dekripcija</span>
            </div>
          </div>
          <div className="smart-info-card-tip">
            Savet: Kliknite na Voyo bedž na vrhu da pokrenete primer filma.
          </div>
        </div>

        {/* HRTi Card */}
        <div className="smart-info-card" style={cssVars({ "--card-brand-color": "#06b6d4" })}>
          <div className="smart-info-card-title-wrap">
            <div className="smart-info-card-title">
              <span>🔵</span> HRTi
            </div>
            <div className="smart-info-card-badge text-cyan-400 border-cyan-500/20">
              720p · MULTI
            </div>
          </div>
          <div className="smart-info-card-features">
            <div className="smart-info-card-feature">
              <Check className="w-3.5 h-3.5" /> <span>Kompletan HRTi katalog emisija</span>
            </div>
            <div className="smart-info-card-feature">
              <Check className="w-3.5 h-3.5" /> <span>Paralelno preuzimanje (Multi-threaded)</span>
            </div>
            <div className="smart-info-card-feature">
              <Check className="w-3.5 h-3.5" /> <span>Integrisan HRTi pretraživač</span>
            </div>
          </div>
          <div className="smart-info-card-tip">
            Savet: Unesite ceo URL ili UUID iz HRTi kataloga za analizu.
          </div>
        </div>

        {/* EON Card */}
        <div className="smart-info-card" style={cssVars({ "--card-brand-color": "#10b981" })}>
          <div className="smart-info-card-title-wrap">
            <div className="smart-info-card-title">
              <span>🟢</span> EON TV
            </div>
            <div className="smart-info-card-badge text-emerald-400 border-emerald-500/20">
              1080p · DVR
            </div>
          </div>
          <div className="smart-info-card-features">
            <div className="smart-info-card-feature">
              <Check className="w-3.5 h-3.5" /> <span>EON Video na Zahtev (VOD)</span>
            </div>
            <div className="smart-info-card-feature">
              <Check className="w-3.5 h-3.5" /> <span>Uživo IPTV snimanje & DVR</span>
            </div>
            <div className="smart-info-card-feature">
              <Check className="w-3.5 h-3.5" /> <span>EPG zakazivanje iz TV vodiča</span>
            </div>
          </div>
          <div className="smart-info-card-tip">
            Savet: Zakazivanje DVR-a radi u pozadini čak i kad zatvorite aplikaciju.
          </div>
        </div>

        {/* RTS Card */}
        <div className="smart-info-card" style={cssVars({ "--card-brand-color": "#f43f5e" })}>
          <div className="smart-info-card-title-wrap">
            <div className="smart-info-card-title">
              <span>🔴</span> RTS Planeta
            </div>
            <div className="smart-info-card-badge text-rose-400 border-rose-500/20">
              720p · AUTO
            </div>
          </div>
          <div className="smart-info-card-features">
            <div className="smart-info-card-feature">
              <Check className="w-3.5 h-3.5" /> <span>TV arhiv, serije i RTS emisije</span>
            </div>
            <div className="smart-info-card-feature">
              <Check className="w-3.5 h-3.5" /> <span>Verbose logovi za lakše praćenje</span>
            </div>
            <div className="smart-info-card-feature">
              <Check className="w-3.5 h-3.5" /> <span>Automatska ekstrakcija tokena</span>
            </div>
          </div>
          <div className="smart-info-card-tip">
            Savet: RTS Planeta nalog mora biti ulogovan/aktivan za preuzimanje.
          </div>
        </div>

        {/* HBO Card */}
        <div className="smart-info-card" style={cssVars({ "--card-brand-color": "#9333ea" })}>
          <div className="smart-info-card-title-wrap">
            <div className="smart-info-card-title">
              <span>🟣</span> HBO Max
            </div>
            <div className="smart-info-card-badge text-purple-400 border-purple-500/20">
              1080p · BYPASS
            </div>
          </div>
          <div className="smart-info-card-features">
            <div className="smart-info-card-feature">
              <Check className="w-3.5 h-3.5" /> <span>Višejezični prevodi (sr, hr, bs...)</span>
            </div>
            <div className="smart-info-card-feature">
              <Check className="w-3.5 h-3.5" /> <span>Bypass režim (Manifest + Licenca)</span>
            </div>
            <div className="smart-info-card-feature">
              <Check className="w-3.5 h-3.5" /> <span>Automatsko dekriptovanje & muxing</span>
            </div>
          </div>
          <div className="smart-info-card-tip">
            Savet: Koristite Bypass za direktno preuzimanje detektovanih resursa.
          </div>
        </div>

        {/* Universal Card */}
        <div className="smart-info-card" style={cssVars({ "--card-brand-color": "#3b82f6" })}>
          <div className="smart-info-card-title-wrap">
            <div className="smart-info-card-title">
              <span>🌐</span> Univerzalno
            </div>
            <div className="smart-info-card-badge text-blue-400 border-blue-500/20">
              {status?.services?.ytdlp && (status.services.ytdlp as { ytdlp_version?: string }).ytdlp_version
                ? `yt-dlp ${(status.services.ytdlp as { ytdlp_version?: string }).ytdlp_version}`
                : "do 4K · yt-dlp"}
            </div>
          </div>
          <div className="smart-info-card-features">
            <div className="smart-info-card-feature">
              <Check className="w-3.5 h-3.5" /> <span>YouTube, X, Facebook, Instagram</span>
            </div>
            <div className="smart-info-card-feature">
              <Check className="w-3.5 h-3.5" /> <span>TikTok, Vimeo, Twitch i 1000+ sajtova</span>
            </div>
            <div className="smart-info-card-feature">
              <Check className="w-3.5 h-3.5" /> <span>Metadata sličice, opisi i naslovi</span>
            </div>
          </div>
          <div className="smart-info-card-tip">
            Savet: Nalepite bilo koji javni link i skener će sam prepoznati format.
          </div>
        </div>

      </div>
    </div>
  </div>
  );
}
