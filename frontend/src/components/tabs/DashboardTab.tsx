import { useState } from "react";
import {
  Check,
  ChevronDown,
  Copy,
  Download,
  Globe,
  Info,
  Loader2,
  Lock,
  Search,
  Sliders,
  Sparkles,
  Zap,
} from "lucide-react";
import { CustomSelect } from "../CustomSelect";
import type { ServiceStatus, SmartEpisode } from "../../types/app";
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
  } = useSmartDashboardTab();

  const [advancedOpen, setAdvancedOpen] = useState(false);
// Service theme config
  const SVC_THEMES: Record<string, {emoji:string; name:string; color:string; glow:string; example:string; exampleLabel:string}> = {
    voyo:    { emoji:"🟠", name:"Voyo",        color:"#f97316", glow:"rgba(249,115,22,0.08)",   example:"https://voyo.rs/uspeh-1_50584.html", exampleLabel:"Film (video ID)" },
    hrti:    { emoji:"🔵", name:"HRTi",        color:"#06b6d4", glow:"rgba(6,182,212,0.08)",    example:"https://hrti.hrt.hr/video/show/4a3b2c1d-0000-0000-0000-000000000001", exampleLabel:"Video (UUID)" },
    eon:     { emoji:"🟢", name:"EON TV",      color:"#10b981", glow:"rgba(16,185,129,0.08)",   example:"https://eon.tv/player/vod-abc123", exampleLabel:"VOD naslov" },
    rts:     { emoji:"🔴", name:"RTS Planeta", color:"#f43f5e", glow:"rgba(244,63,94,0.08)",    example:"https://www.rtsplaneta.rs/video/show/12345", exampleLabel:"Epizoda/emisija" },
    rtsplaneta: { emoji:"🔴", name:"RTS Planeta", color:"#f43f5e", glow:"rgba(244,63,94,0.08)", example:"https://www.rtsplaneta.rs/video/show/12345", exampleLabel:"Epizoda/emisija" },
    hbomax:  { emoji:"🟣", name:"HBO Max",     color:"#9333ea", glow:"rgba(147,51,234,0.08)",   example:"https://www.max.com/show/urn:hbo:episode:xyz123", exampleLabel:"Epizoda/film" },
    ytdlp:   { emoji:"🌐", name:"Univerzalno",  color:"#3b82f6", glow:"rgba(59,130,246,0.08)",   example:"https://www.youtube.com/watch?v=dQw4w9WgXcQ", exampleLabel:"YouTube, X, TikTok, FB..." },
  };
  const svcKeys = Object.keys(SVC_THEMES).filter(k => k !== "rtsplaneta");
  // Service auth sub-text (from status if available)
  const getSvcStatus = (k: string) => {
    if (k === "ytdlp") return { online: true, label: "Uvek aktivno" };
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
                {st.online ? "AKTIVAN" : "OFF"}
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

    <div className="flex flex-col gap-5 max-w-4xl mx-auto w-full">

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
              {smartData.description && <p className="smart-preview-desc">{smartData.description}</p>}
              {/* Extra metadata pills for yt-dlp */}
              {smartData.service === "ytdlp" && (smartData.duration_str || smartData.uploader || smartData.view_count != null || smartData.upload_date) && (
                <div style={{display:"flex", flexWrap:"wrap", gap:"6px", marginTop:"10px"}}>
                  {smartData.duration_str && (
                    <span style={{display:"inline-flex",alignItems:"center",gap:4,fontSize:"0.72rem",fontWeight:700,color:"var(--text-secondary)",background:"rgba(255,255,255,0.04)",border:"1px solid rgba(255,255,255,0.07)",borderRadius:6,padding:"3px 8px"}}>
                      <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
                      {smartData.duration_str}
                    </span>
                  )}
                  {smartData.uploader && (
                    <span style={{display:"inline-flex",alignItems:"center",gap:4,fontSize:"0.72rem",fontWeight:700,color:"var(--text-secondary)",background:"rgba(255,255,255,0.04)",border:"1px solid rgba(255,255,255,0.07)",borderRadius:6,padding:"3px 8px"}}>
                      <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
                      {smartData.uploader}
                    </span>
                  )}
                  {smartData.view_count != null && (
                    <span style={{display:"inline-flex",alignItems:"center",gap:4,fontSize:"0.72rem",fontWeight:700,color:"var(--text-secondary)",background:"rgba(255,255,255,0.04)",border:"1px solid rgba(255,255,255,0.07)",borderRadius:6,padding:"3px 8px"}}>
                      <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
                      {smartData.view_count >= 1_000_000
                        ? `${(smartData.view_count / 1_000_000).toFixed(1)}M pregleda`
                        : smartData.view_count >= 1_000
                        ? `${(smartData.view_count / 1_000).toFixed(0)}K pregleda`
                        : `${smartData.view_count} pregleda`}
                    </span>
                  )}
                  {smartData.upload_date && (
                    <span style={{display:"inline-flex",alignItems:"center",gap:4,fontSize:"0.72rem",fontWeight:700,color:"var(--text-secondary)",background:"rgba(255,255,255,0.04)",border:"1px solid rgba(255,255,255,0.07)",borderRadius:6,padding:"3px 8px"}}>
                      <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>
                      {smartData.upload_date}
                    </span>
                  )}
                </div>
              )}
            </div>
          </div>

          {/* Body */}
          <div className="smart-preview-body">
            {/* Episode checklist (series with episodes) */}
            {smartData.episodes && smartData.episodes.length > 0 && (
              <div>
                <div style={{display:"flex", justifyContent:"space-between", alignItems:"center", marginBottom:10}}>
                  <label style={{margin:0}}>
                    Epizode ({smartSelectedEpisodes.length}/{smartData.episodes.length} odabrano)
                  </label>
                  <div style={{display:"flex", gap:12}}>
                    <button
                      style={{fontSize:"0.72rem", fontWeight:700, color:previewTheme.color, background:"none", border:"none", cursor:"pointer"}}
                      onClick={() => setSmartSelectedEpisodes(smartData.episodes!.map((e: SmartEpisode) => e.id))}
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
                    const checked = smartSelectedEpisodes.includes(ep.id);
                    return (
                      <div
                        key={ep.id ?? idx}
                        className={`smart-ep-item ${checked ? "selected" : ""}`}
                        onClick={() => setSmartSelectedEpisodes(checked
                          ? smartSelectedEpisodes.filter((id: number | string) => id !== ep.id)
                          : [...smartSelectedEpisodes, ep.id]
                        )}
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
                        {ep.drm && <Lock style={{width:12,height:12,color:"#f59e0b",flexShrink:0}} />}
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* Config row */}
            <div className="smart-config-row">
              {(smartData.service === "voyo" || smartData.service === "ytdlp") && (
                <div>
                  <label>Rezolucija</label>
                  <CustomSelect
                    value={smartResolution}
                    options={smartData.service === "ytdlp" && smartData.available_resolutions && smartData.available_resolutions.length > 0 
                      ? smartData.available_resolutions 
                      : ["1080p (Full HD)", "720p (HD)", "480p (SD)"]
                    }
                    onChange={(val) => setSmartResolution(val)}
                    formatLabel={(val) => {
                      // Labels are already descriptive from backend (e.g. "2160p (4K)")
                      return val;
                    }}
                  />
                </div>
              )}
              {(smartData.service === "hbomax" || smartData.service === "ytdlp") && (() => {
                const activeList = smartSubs ? smartSubs.split(",").map((s: string) => s.trim().toLowerCase()).filter(Boolean) : [];
                const toggleLang = (lang: string) => {
                  const l = lang.toLowerCase();
                  if (activeList.includes(l)) {
                    setSmartSubs(activeList.filter((s: string) => s !== l).join(","));
                  } else {
                    setSmartSubs([...activeList, l].join(","));
                  }
                };
                return (
                  <div>
                    <label>Prevodi (odaberi klikom na oznaku jezika)</label>
                    <input type="text" value={smartSubs} onChange={e=>setSmartSubs(e.target.value)}
                      placeholder={smartData.service === "hbomax" ? "sr,hr,mk,bs,sl" : "npr. en,sr,hr ili all (ostavi prazno za bez prevoda)"}
                      className="py-2.5 px-3 bg-black/40 border border-glass text-white rounded focus:outline-none w-full" />
                    
                    {smartData.service === "ytdlp" && (
                      <div className="mt-2.5 flex flex-col gap-2 bg-black/25 p-3 rounded-lg border border-white/[0.04]">
                        {/* Manual Subtitles */}
                        {smartData.available_subtitles && smartData.available_subtitles.length > 0 && (
                          <div>
                            <div className="text-[10px] text-text-muted font-bold mb-1 uppercase tracking-wider">Detektovani prevodi (izvor):</div>
                            <div className="flex flex-wrap gap-1.5">
                              {smartData.available_subtitles.map((lang: string) => {
                                const isSel = activeList.includes(lang.toLowerCase());
                                return (
                                  <button
                                    key={lang}
                                    onClick={() => toggleLang(lang)}
                                    className={`px-2 py-1 rounded text-[10px] font-bold border transition-all ${
                                      isSel 
                                        ? "bg-blue-500/20 text-blue-400 border-blue-500/40 shadow-[0_0_8px_rgba(59,130,246,0.25)]" 
                                        : "bg-white/[0.02] text-text-secondary border-white/[0.04] hover:bg-white/[0.05]"
                                    }`}
                                  >
                                    {lang.toUpperCase()}
                                  </button>
                                );
                              })}
                            </div>
                          </div>
                        )}
                        
                        {/* Auto Subtitles */}
                        {smartData.available_auto_subtitles && smartData.available_auto_subtitles.length > 0 && (
                          <div>
                            <div className="text-[10px] text-text-muted font-bold mb-1 uppercase tracking-wider">Automatski titlovi (AI generisani):</div>
                            <div className="flex flex-wrap gap-1.5 max-h-24 overflow-y-auto pr-1">
                              {smartData.available_auto_subtitles.map((lang: string) => {
                                const isSel = activeList.includes(lang.toLowerCase());
                                return (
                                  <button
                                    key={lang}
                                    onClick={() => toggleLang(lang)}
                                    className={`px-2 py-1 rounded text-[10px] font-bold border transition-all ${
                                      isSel 
                                        ? "bg-amber-500/20 text-amber-400 border-amber-500/40 shadow-[0_0_8px_rgba(245,158,11,0.25)]" 
                                        : "bg-white/[0.02] text-text-secondary border-white/[0.04] hover:bg-white/[0.05]"
                                    }`}
                                  >
                                    {lang.toUpperCase()}
                                  </button>
                                );
                              })}
                            </div>
                          </div>
                        )}
                        
                        <div className="flex gap-2.5 mt-1 border-t border-white/[0.03] pt-2">
                          <button
                            onClick={() => setSmartSubs("all")}
                            className="text-[9px] font-extrabold text-blue-400 hover:underline bg-none border-none cursor-pointer"
                          >
                            Uključi sve jezike ("all")
                          </button>
                          <span className="text-white/[0.08] text-[9px]">|</span>
                          <button
                            onClick={() => setSmartSubs("")}
                            className="text-[9px] font-extrabold text-text-muted hover:underline bg-none border-none cursor-pointer"
                          >
                            Isključi sve prevode
                          </button>
                        </div>
                      </div>
                    )}
                  </div>
                );
              })()}
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
              
              {smartData.service === "ytdlp" && (
                <div style={{ gridColumn: "1 / -1", display: "flex", flexDirection: "column", gap: "16px", marginTop: "12px" }}>
                  <div className="flex gap-4 items-center flex-wrap">
                    <label className="custom-checkbox-wrap" style={{ cursor: "pointer" }}>
                      <input
                        type="checkbox"
                        checked={smartAudioOnly}
                        onChange={e => setSmartAudioOnly(e.target.checked)}
                      />
                      <div className={`custom-checkbox-box ${smartAudioOnly ? "checked" : ""}`} style={smartAudioOnly ? {background:"#3b82f6", borderColor:"#3b82f6"} : {}}>
                        <svg className="custom-checkbox-check" viewBox="0 0 10 10" fill="none" stroke="white" strokeWidth="2">
                          <polyline points="1.5 5 4 7.5 8.5 2" />
                        </svg>
                      </div>
                      <span className="text-xs font-semibold text-white">Preuzmi samo audio (MP3)</span>
                    </label>

                    <label className="custom-checkbox-wrap" style={{ cursor: "pointer" }}>
                      <input
                        type="checkbox"
                        checked={smartUseAria2}
                        onChange={e => setSmartUseAria2(e.target.checked)}
                      />
                      <div className={`custom-checkbox-box ${smartUseAria2 ? "checked" : ""}`} style={smartUseAria2 ? {background:"#3b82f6", borderColor:"#3b82f6"} : {}}>
                        <svg className="custom-checkbox-check" viewBox="0 0 10 10" fill="none" stroke="white" strokeWidth="2">
                          <polyline points="1.5 5 4 7.5 8.5 2" />
                        </svg>
                      </div>
                      <span className="text-xs font-semibold text-white flex items-center gap-1">
                        Aria2 Ubrzanje <Sparkles className="w-3 h-3 text-amber-400 animate-pulse" />
                      </span>
                    </label>
                  </div>

                  {/* Accordion za napredna podešavanja */}
                  <div className={`ytdlp-advanced-accordion ${advancedOpen ? "open" : ""}`}>
                    <button
                      type="button"
                      className="ytdlp-advanced-header"
                      onClick={() => setAdvancedOpen(!advancedOpen)}
                    >
                      <span className="ytdlp-advanced-header-title">
                        <Sliders className="w-4 h-4 text-blue-400" />
                        Napredna podešavanja preuzimanja (yt-dlp)
                      </span>
                      <ChevronDown className={`ytdlp-advanced-chevron w-4 h-4 ${advancedOpen ? "rotated" : ""}`} />
                    </button>
                    {advancedOpen && (
                      <div className="ytdlp-advanced-content">
                        <div className="ytdlp-advanced-grid">
                          <div className="ytdlp-advanced-field">
                            <label>Uvoz kolačića (Cookies)</label>
                            <CustomSelect
                              value={ytdlpCookiesBrowser ? (ytdlpCookiesBrowser.charAt(0).toUpperCase() + ytdlpCookiesBrowser.slice(1)) : "Bez uvoza"}
                              options={["Bez uvoza", "Chrome", "Edge", "Firefox", "Brave"]}
                              onChange={(val) => setYtdlpCookiesBrowser(val === "Bez uvoza" ? "" : val.toLowerCase())}
                            />
                          </div>
                          <div className="ytdlp-advanced-field">
                            <label>Proksi (Proxy) URL</label>
                            <input
                              type="text"
                              value={ytdlpProxy}
                              onChange={e => setYtdlpProxy(e.target.value)}
                              placeholder="npr. http://127.0.0.1:8080"
                              className="ytdlp-advanced-input"
                            />
                          </div>
                          <div className="ytdlp-advanced-field">
                            <label>Limit brzine preuzimanja</label>
                            <input
                              type="text"
                              value={ytdlpLimitRate}
                              onChange={e => setYtdlpLimitRate(e.target.value)}
                              placeholder="npr. 50K ili 5M"
                              className="ytdlp-advanced-input"
                            />
                          </div>
                        </div>

                        <div className="ytdlp-advanced-checkboxes">
                          <label className="custom-checkbox-wrap" style={{ cursor: "pointer" }}>
                            <input
                              type="checkbox"
                              checked={ytdlpImpersonate}
                              onChange={e => setYtdlpImpersonate(e.target.checked)}
                            />
                            <div className={`custom-checkbox-box ${ytdlpImpersonate ? "checked" : ""}`} style={ytdlpImpersonate ? {background:"#3b82f6", borderColor:"#3b82f6"} : {}}>
                              <svg className="custom-checkbox-check" viewBox="0 0 10 10" fill="none" stroke="white" strokeWidth="2">
                                <polyline points="1.5 5 4 7.5 8.5 2" />
                              </svg>
                            </div>
                            <span className="text-xs font-semibold text-white">Browser Impersonation (Chrome)</span>
                          </label>

                          <label className="custom-checkbox-wrap" style={{ cursor: "pointer" }}>
                            <input
                              type="checkbox"
                              checked={ytdlpGeoBypass}
                              onChange={e => setYtdlpGeoBypass(e.target.checked)}
                            />
                            <div className={`custom-checkbox-box ${ytdlpGeoBypass ? "checked" : ""}`} style={ytdlpGeoBypass ? {background:"#3b82f6", borderColor:"#3b82f6"} : {}}>
                              <svg className="custom-checkbox-check" viewBox="0 0 10 10" fill="none" stroke="white" strokeWidth="2">
                                <polyline points="1.5 5 4 7.5 8.5 2" />
                              </svg>
                            </div>
                            <span className="text-xs font-semibold text-white">Geo-Bypass (Zaobilaženje restrikcija)</span>
                          </label>

                          <label className="custom-checkbox-wrap" style={{ cursor: "pointer" }}>
                            <input
                              type="checkbox"
                              checked={ytdlpEmbedThumbnail}
                              onChange={e => setYtdlpEmbedThumbnail(e.target.checked)}
                            />
                            <div className={`custom-checkbox-box ${ytdlpEmbedThumbnail ? "checked" : ""}`} style={ytdlpEmbedThumbnail ? {background:"#3b82f6", borderColor:"#3b82f6"} : {}}>
                              <svg className="custom-checkbox-check" viewBox="0 0 10 10" fill="none" stroke="white" strokeWidth="2">
                                <polyline points="1.5 5 4 7.5 8.5 2" />
                              </svg>
                            </div>
                            <span className="text-xs font-semibold text-white">Ugradi sličicu (Thumbnail) u video</span>
                          </label>

                          <label className="custom-checkbox-wrap" style={{ cursor: "pointer" }}>
                            <input
                              type="checkbox"
                              checked={ytdlpEmbedMetadata}
                              onChange={e => setYtdlpEmbedMetadata(e.target.checked)}
                            />
                            <div className={`custom-checkbox-box ${ytdlpEmbedMetadata ? "checked" : ""}`} style={ytdlpEmbedMetadata ? {background:"#3b82f6", borderColor:"#3b82f6"} : {}}>
                              <svg className="custom-checkbox-check" viewBox="0 0 10 10" fill="none" stroke="white" strokeWidth="2">
                                <polyline points="1.5 5 4 7.5 8.5 2" />
                              </svg>
                            </div>
                            <span className="text-xs font-semibold text-white">Ugradi metapodatke i poglavlja</span>
                          </label>
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>

            {/* CTA */}
            <div style={{display:"flex", alignItems:"center", gap:14}}>
              <button
                className={`smart-cta-btn smart-cta-${smartData.service}`}
                onClick={startSmartDownload}
                disabled={smartSubmitting || (smartData.episodes && smartSelectedEpisodes.length === 0)}
              >
                {smartSubmitting
                  ? <Loader2 style={{width:18,height:18,animation:"spin 1s linear infinite"}} />
                  : <Download style={{width:18,height:18}} />
                }
                {smartSubmitting
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
                  setAdvancedOpen(false);
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
    <div className="mt-2 w-full max-w-5xl mx-auto flex flex-col gap-3">
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
              do 4K · yt-dlp
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
