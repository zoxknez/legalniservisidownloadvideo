import {
  Clock,
  Download,
  FileText,
  Film,
  Globe,
  Hash,
  List,
  Lock,
  Play,
  Search,
  ShieldAlert,
  User,
  X,
} from "lucide-react";
import { CustomSelect } from "../CustomSelect";
import { apiFetch } from "../../lib/api";
import type { EonMediaItem, ScheduledTask } from "../../types/app";
import { useEonTab } from "../../hooks/domains/useEonTab";
import { cssVars } from "../../utils/cssVars";

export function EonTab() {
  const {
    binariesPaths,
    deviceWvdInfo,
    fetchScheduledRecordings,
    handleSaveDeviceWvdPath,
    scheduledTasks,
    setBinariesPaths,
    showToast,
    submitLogin,
    eonCatalogPath,
    eonChannels,
    eonDuration,
    eonEpgItems,
    eonEpisodesRange,
    eonLiveInputMode,
    eonMissing,
    eonMode,
    eonNumber,
    eonOptionalMissing,
    eonPassword,
    eonPlay,
    eonPlayerPath,
    eonReady,
    eonSearchQuery,
    eonSearchResults,
    eonSerial,
    eonStatus,
    eonTarget,
    eonUsername,
    fetchEonEpg,
    initEonCatalogs,
    loginEonApi,
    refreshEonApiToken,
    scheduleEonRecording,
    searchEonVod,
    setEonDuration,
    setEonEpisodesRange,
    setEonLiveInputMode,
    setEonMode,
    setEonNumber,
    setEonPassword,
    setEonPlay,
    setEonPlayerPath,
    setEonSearchQuery,
    setEonSerial,
    setEonTarget,
    setEonUsername,
    setShowEonPass,
    showEonPass,
    startEonDownload,
  } = useEonTab();
  return (
<div key="eon" className="tab-content tab-content-eon">
    <div className="tab-page-header tab-header-eon mb-8">
      <div className="tab-page-header-icon animate-pulse" style={{background:"linear-gradient(135deg,#10b981,#059669)"}}>
        <Play style={{width:24,height:24,color:"white"}} />
      </div>
      <div style={{flex:1}}>
        <div className="flex items-center justify-between flex-wrap gap-2">
          <h2 className="text-2xl font-extrabold text-white mb-1 flex items-center gap-2.5">
            <Play className="w-6 h-6 text-emerald-400" /> EON TV
          </h2>
          <span className="badge flex items-center gap-1.5 bg-emerald-500/10 border-emerald-500/30 text-emerald-400 font-black px-2.5 py-1 text-[10px] tracking-wider rounded-md">
            <Lock className="w-3.5 h-3.5" /> WIDEVINE L3 DEKRIPCIJA AKTIVNA
          </span>
        </div>
        <p className="text-text-secondary text-sm">VOD sadržaj, serije i TV kanali uživo sa Widevine DRM dekripcijom i API katalogom.</p>
      </div>
    </div>

    {eonStatus && !eonReady && (
      <div className="mb-6 p-5 rounded-xl border border-amber-500/20 bg-amber-500/10 flex flex-col gap-2.5 glow-amber-card glow-card-premium transition-all">
        <div className="flex items-center gap-2 text-amber-300 font-extrabold text-sm">
          <ShieldAlert className="w-5 h-5 animate-pulse" />
          EON Nije Spreman
        </div>
        <p className="text-xs text-text-secondary">{eonStatus.error || "Proverite EON konfiguraciju."}</p>
        {eonMissing.length > 0 && (
          <p className="text-[10px] text-text-muted font-mono bg-black/30 p-2 rounded border border-white/[0.02] break-all">
            Nedostaje: {eonMissing.join(", ")}
          </p>
        )}
        {eonOptionalMissing.length > 0 && (
          <p className="text-[10px] text-text-muted font-mono bg-black/30 p-2 rounded border border-white/[0.02] break-all">
            Opciono nedostaje: {eonOptionalMissing.join(", ")}
          </p>
        )}
      </div>
    )}

    <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
      
      <div className="md:col-span-2 glass-panel p-8 rounded-xl border border-glass flex flex-col gap-6 glow-green-card glow-card-premium">
        <div>
          <label>Mod Rada (EON)</label>
          <div className="sliding-tabs-wrapper">
            <div
              className="sliding-tabs-slider"
              style={{
                width: "calc(33.333% - 4px)",
                transform: `translateX(${eonMode === "vod" ? "0%" : eonMode === "series" ? "100%" : "200%"})`
              }}
            />
            {["vod", "series", "live"].map((mode) => (
              <button
                key={mode}
                type="button"
                onClick={() => { setEonTarget(""); setEonMode(mode as "vod" | "series" | "live"); }}
                className={`sliding-tabs-btn ${eonMode === mode ? "active" : ""}`}
              >
                {mode === "vod" && "VOD / URL"}
                {mode === "series" && "Epizode / Serije"}
                {mode === "live" && "TV Uživo (Live)"}
              </button>
            ))}
          </div>
        </div>

        {eonMode === "live" ? (
          <div className="flex flex-col gap-3">
            <div>
              <label>Mod unosa TV kanala</label>
              <div className="sliding-tabs-wrapper mb-2">
                <div
                  className="sliding-tabs-slider"
                  style={{
                    width: "calc(50% - 4px)",
                    transform: `translateX(${eonLiveInputMode === "catalog" ? "0%" : "100%"})`
                  }}
                />
                <button
                  type="button"
                  onClick={() => { setEonLiveInputMode("catalog"); setEonTarget(""); }}
                  className={`sliding-tabs-btn text-xs ${eonLiveInputMode === "catalog" ? "active" : ""}`}
                >
                  Izaberi iz liste
                </button>
                <button
                  type="button"
                  onClick={() => { setEonLiveInputMode("url"); setEonTarget(""); }}
                  className={`sliding-tabs-btn text-xs ${eonLiveInputMode === "url" ? "active" : ""}`}
                >
                  Direktan live URL
                </button>
              </div>
            </div>

            {eonLiveInputMode === "catalog" ? (
              <div>
                <label>Izaberite TV Kanal</label>
                <CustomSelect
                  value={eonTarget}
                  options={eonChannels}
                  onChange={(val) => setEonTarget(val)}
                  placeholder="-- Izaberi kanal iz liste --"
                  searchPlaceholder="Pretraži kanale..."
                />
                <p className="text-[10px] text-text-muted mt-1.5">Lista se čita iz eon_channels.json ako ga napravite u rootu aplikacije ili ~/.videodownload.</p>
              </div>
            ) : (
              <div>
                <label>Direktan Live URL (.m3u8 / .mpd)</label>
                <div className="password-wrapper">
                  <Globe className="absolute left-4 text-text-muted w-4 h-4" />
                  <input
                    type="text"
                    placeholder="npr. https://.../live/index.m3u8"
                    value={eonTarget}
                    onChange={(e) => setEonTarget(e.target.value)}
                    className="input-premium pl-11"
                    style={cssVars({"--focused-border": "#10b981", "--focused-glow": "rgba(16,185,129,0.25)"})}
                  />
                </div>
                <p className="text-[10px] text-text-muted mt-1.5">Zalepite m3u8 manifest link iz browsera ili m3u8 strim.</p>
              </div>
            )}
          </div>
        ) : (
          <div>
            <label>{eonMode === "vod" ? "Direktan VOD media URL" : "Series ID iz lokalnog kataloga"}</label>
            <div className="password-wrapper">
              {eonMode === "vod" ? (
                <Film className="absolute left-4 text-text-muted w-4 h-4" />
              ) : (
                <List className="absolute left-4 text-text-muted w-4 h-4" />
              )}
              <input
                type="text"
                placeholder={eonMode === "vod" ? "npr. https://.../video.m3u8 ili .mpd/.mp4" : "npr. 162073-s1"}
                value={eonTarget}
                onChange={(e) => setEonTarget(e.target.value)}
                className="input-premium pl-11"
                style={cssVars({"--focused-border": "#10b981", "--focused-glow": "rgba(16,185,129,0.25)"})}
              />
            </div>
            <p className="text-[10px] text-text-muted mt-1.5">
              {eonMode === "vod"
                ? "Unesite EON VOD ID (npr. sa linka /ondemand/detail/12345), manifest URL ili direktan video link."
                : "Epizode se čitaju iz EON API-ja ili lokalnog eon_series.json fajla."}
            </p>
          </div>
        )}

        {eonMode === "live" && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              {/* F5: Default 3600s (1h) */}
              <label>Trajanje snimanja (sekunde)</label>
              <div className="password-wrapper">
                <Clock className="absolute left-4 text-text-muted w-4 h-4" />
                <input
                  type="number"
                  value={eonDuration}
                  onChange={(e) => setEonDuration(parseInt(e.target.value) || 0)}
                  className="input-premium pl-11"
                  style={cssVars({"--focused-border": "#10b981", "--focused-glow": "rgba(16,185,129,0.25)"})}
                />
              </div>
              <p className="text-[10px] text-text-muted mt-1">
                * 0 = snimaj bez prestanka &nbsp;|&nbsp; 3600 = 1 sat &nbsp;|&nbsp; 7200 = 2 sata
              </p>
            </div>

            <div className="flex flex-col justify-end">
              <label className="flex items-center gap-3 p-3 rounded border border-glass cursor-pointer select-none">
                <input
                  type="checkbox"
                  className="w-4 h-4 cursor-pointer"
                  checked={eonPlay}
                  onChange={(e) => setEonPlay(e.target.checked)}
                />
                <span className="text-sm font-semibold text-white">Gledaj tokom snimanja</span>
              </label>
            </div>
          </div>
        )}

        {eonMode === "live" && eonPlay && (
          <div>
            <label>Putanja do video plejera (VLC/MPV - Opciono)</label>
            <div className="password-wrapper">
              <Play className="absolute left-4 text-text-muted w-4 h-4" />
              <input
                type="text"
                placeholder="npr. C:\Program Files\VideoLAN\VLC\vlc.exe"
                value={eonPlayerPath}
                onChange={(e) => setEonPlayerPath(e.target.value)}
                className="input-premium pl-11"
                style={cssVars({"--focused-border": "#10b981", "--focused-glow": "rgba(16,185,129,0.25)"})}
              />
            </div>
          </div>
        )}

        {eonMode === "series" && (
          <div>
            <label>Raspon Epizoda</label>
            <div className="password-wrapper">
              <Hash className="absolute left-4 text-text-muted w-4 h-4" />
              <input
                type="text"
                placeholder="npr. 1-3, 2-, -5, 4 (ostavi prazno za sve epizode)"
                value={eonEpisodesRange}
                onChange={(e) => setEonEpisodesRange(e.target.value)}
                className="input-premium pl-11"
                style={cssVars({"--focused-border": "#10b981", "--focused-glow": "rgba(16,185,129,0.25)"})}
              />
            </div>
          </div>
        )}

        {eonMode === "vod" && (
          <div className="border-t border-glass pt-5 flex flex-col gap-3">
            <label>Pretraga VOD kataloga</label>
            <div className="password-wrapper w-full">
              <Search className="absolute left-4 text-text-muted w-4 h-4" />
              <input
                type="text"
                value={eonSearchQuery}
                onChange={(e) => setEonSearchQuery(e.target.value)}
                placeholder="Pretraži lokalni katalog ili API"
                className="input-premium pl-11 pr-24"
                style={cssVars({"--focused-border": "#10b981", "--focused-glow": "rgba(16,185,129,0.25)"})}
              />
              <button
                onClick={searchEonVod}
                className="btn btn-premium-primary absolute right-1.5 top-1.5 bottom-1.5 h-auto py-1 px-4 text-xs font-bold"
                style={cssVars({
                  "--btn-grad-start": "#10b981",
                  "--btn-grad-end": "#059669",
                  "--btn-glow": "rgba(16,185,129,0.25)",
                  "--btn-glow-hover": "rgba(16,185,129,0.45)",
                  height: "calc(100% - 6px)",
                  display: "flex",
                  alignItems: "center"
                })}
              >
                Pretraži
              </button>
            </div>
            {eonSearchResults.length > 0 && (
              <div className="flex flex-col gap-2 mt-2">
                {eonSearchResults.slice(0, 6).map((item: EonMediaItem, idx: number) => {
                  const label = item.title || item.name || item.id || `Rezultat ${idx + 1}`;
                  const target = item.url || item.id || label;
                  return (
                    <button
                      key={`${label}-${idx}`}
                      onClick={() => setEonTarget(target)}
                      className="text-left p-3 rounded-lg border border-glass bg-white/[0.02] hover:bg-white/[0.05] transition"
                    >
                      <span className="block text-sm font-bold text-white">{label}</span>
                      <span className="block text-[10px] text-text-muted font-mono truncate">{target}</span>
                    </button>
                  );
                })}
              </div>
            )}
          </div>
        )}

        {eonMode === "live" && eonTarget && (
          <div className="border-t border-glass pt-5 flex flex-col gap-3">
            <button onClick={fetchEonEpg} className="btn btn-secondary text-xs self-start">
              Učitaj EPG za kanal
            </button>
            {eonEpgItems.length > 0 && (
              <div className="flex flex-col gap-2">
                {eonEpgItems.slice(0, 5).map((item: EonMediaItem, idx: number) => {
                  const isFuture = item.start && new Date(item.start) > new Date();
                  return (
                    <div key={idx} className="p-3 rounded-lg border border-glass bg-white/[0.02] flex items-center justify-between gap-4">
                      <div className="flex-1">
                        <p className="text-sm font-bold text-white">{item.title || item.name || `Program ${idx + 1}`}</p>
                        <p className="text-[10px] text-text-muted">{item.start || ""} {item.end ? `- ${item.end}` : ""}</p>
                        {item.description && <p className="text-xs text-text-secondary mt-1">{item.description}</p>}
                      </div>
                      {isFuture && (
                        <button
                          onClick={() => {
                            const durMin = item.duration_min || 60;
                            scheduleEonRecording(eonTarget, item.title || `EON ${eonTarget}`, item.start ?? "", durMin);
                          }}
                          className="btn btn-premium-secondary py-1 px-2.5 text-[10px] gap-1 flex-shrink-0"
                          style={cssVars({
                            "--btn-grad-start": "#10b981",
                            "--btn-grad-end": "#059669",
                            "--btn-glow": "rgba(16,185,129,0.15)",
                            "--btn-glow-hover": "rgba(16,185,129,0.3)"
                          })}
                        >
                          <Clock className="w-3.5 h-3.5" /> Zakaži
                        </button>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
            
            {/* Custom DVR Schedule Form */}
            <div className="border-t border-white/[0.04] pt-4 mt-2 flex flex-col gap-3">
              <h4 className="text-xs font-bold text-emerald-400">🕒 Ručno zakaži snimanje</h4>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="text-[10px] text-text-muted">Početak (ISO format / Vreme)</label>
                  <input
                    type="datetime-local"
                    id="dvr_start_time"
                    className="input-premium py-1 text-xs"
                    style={cssVars({"--focused-border": "#10b981", "--focused-glow": "rgba(16,185,129,0.25)"})}
                  />
                </div>
                <div>
                  <label className="text-[10px] text-text-muted">Trajanje (Minuti)</label>
                  <input
                    type="number"
                    id="dvr_duration"
                    placeholder="60"
                    defaultValue="60"
                    className="input-premium py-1 text-xs"
                    style={cssVars({"--focused-border": "#10b981", "--focused-glow": "rgba(16,185,129,0.25)"})}
                  />
                </div>
              </div>
              <button
                onClick={() => {
                  const startEl = document.getElementById("dvr_start_time") as HTMLInputElement;
                  const durEl = document.getElementById("dvr_duration") as HTMLInputElement;
                  const startTime = startEl?.value ? new Date(startEl.value).toISOString() : new Date().toISOString();
                  const duration = parseInt(durEl?.value || "60");
                  scheduleEonRecording(eonTarget, `DVR Snimanje: ${eonTarget}`, startTime, duration);
                }}
                disabled={!eonTarget}
                className="btn btn-premium-secondary py-1.5 text-xs text-white"
                style={cssVars({
                  "--btn-grad-start": "#10b981",
                  "--btn-grad-end": "#059669",
                  "--btn-glow": "rgba(16,185,129,0.15)",
                  "--btn-glow-hover": "rgba(16,185,129,0.3)"
                })}
              >
                Zakaži Ručno
              </button>
            </div>
          </div>
        )}

        <button
          onClick={startEonDownload}
          disabled={!eonTarget || !eonReady}
          className="btn btn-premium-primary w-full py-4 text-white font-bold"
          style={cssVars({
            "--btn-grad-start": "#10b981",
            "--btn-grad-end": "#059669",
            "--btn-glow": "rgba(16,185,129,0.25)",
            "--btn-glow-hover": "rgba(16,185,129,0.45)"
          })}
          title={!eonReady ? "EON engine, credentials or dependencies are missing." : undefined}
        >
          <Download className="w-5 h-5" />
          {eonMode === "live" ? "Započni Snimanje / Stream" : "Započni Preuzimanje"}
        </button>
      </div>

      {/* Status card */}
      <div className="flex flex-col gap-6">
        <div className="glass-panel p-6 rounded-xl border border-glass glow-green-card glow-card-premium">
          <h3 className="font-extrabold text-base mb-4 flex items-center gap-2 text-white">
            <User className="w-5 h-5 text-emerald-400" />
            Status Uređaja / Naloga
          </h3>

          {eonStatus?.ready ? (
            <div className="flex flex-col gap-3">
              <span className="badge flex items-center gap-1.5 bg-emerald-500/10 border-emerald-500/30 text-emerald-400 font-black px-2.5 py-1 text-[10px] tracking-wider rounded-md w-max" style={cssVars({animation: "pulseGlowBrighter 2s infinite", "--glow-color": "rgba(16, 185, 129, 0.2)"})}>
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 shadow-[0_0_8px_#34d399]"></span> EON UREĐAJ SPREMAN
              </span>
              <div className="flex flex-col gap-1.5 border-t border-white/[0.03] pt-3 text-xs text-text-secondary">
                <p className="font-bold text-text-secondary">Korisnički nalog:</p>
                <p className="text-sm font-semibold text-white truncate bg-black/20 p-2 rounded border border-white/[0.02]">{eonStatus.username}</p>
              </div>
              <div className="flex justify-between items-center text-[10px] font-mono text-text-muted bg-black/10 p-2 rounded border border-white/[0.02]">
                <span>Serijski broj:</span>
                <span className="text-white font-bold">{eonStatus.serial}</span>
              </div>
              <div className="flex justify-between items-center text-[10px] font-mono text-text-muted bg-black/10 p-2 rounded border border-white/[0.02]">
                <span>Broj uređaja:</span>
                <span className="text-white font-bold">{eonStatus.number}</span>
              </div>
              
              {/* EON API status details */}
              <div className="border-t border-white/[0.04] pt-3 mt-1 flex flex-col gap-1.5">
                <span className="text-[10px] text-text-muted font-bold uppercase tracking-wider">EON API & CDM status:</span>
                <div className="flex justify-between items-center text-xs">
                  <span className="text-text-secondary">API Konekcija:</span>
                  <span className={eonStatus.engine_status?.api?.configured ? "text-emerald-400 font-bold" : "text-amber-400 font-bold"}>
                    {eonStatus.engine_status?.api?.configured ? "Povezana ✓" : "Nije povezana"}
                  </span>
                </div>
                <div className="flex justify-between items-center text-xs">
                  <span className="text-text-secondary">CDM Decryption:</span>
                  <span className={eonStatus.engine_status?.cdm_ready ? "text-emerald-400 font-bold" : "text-amber-400 font-bold"}>
                    {eonStatus.engine_status?.cdm_ready ? "Učitan ✓" : "device.wvd nedostaje"}
                  </span>
                </div>
                {eonStatus.engine_status?.token?.expires_at && (
                  <div className="flex flex-col text-[10px] text-text-muted mt-1 bg-black/20 p-2 rounded border border-white/[0.02] truncate">
                    <span>Token ističe:</span>
                    <span className="font-mono text-white mt-0.5">{eonStatus.engine_status.token.expires_at}</span>
                  </div>
                )}
              </div>
            </div>
          ) : (
            <div className="flex flex-col gap-3">
              <span className="badge flex items-center gap-1.5 bg-red-500/10 border-red-500/30 text-red-400 font-black px-2.5 py-1 text-[10px] tracking-wider rounded-md w-max">
                <span className="w-1.5 h-1.5 rounded-full bg-red-400 animate-ping"></span> NIJE SPREMAN
              </span>
              <p className="text-xs text-text-secondary leading-relaxed mt-1">{eonStatus?.error || "Registrujte EON nalog i proverite engine/dependencies."}</p>
              
              {/* EON API status details even when not fully ready */}
              <div className="border-t border-white/[0.04] pt-3 mt-1 flex flex-col gap-1.5">
                <span className="text-[10px] text-text-muted font-bold uppercase tracking-wider">EON API & CDM status:</span>
                <div className="flex justify-between items-center text-xs">
                  <span className="text-text-secondary">API Konekcija:</span>
                  <span className={eonStatus?.engine_status?.api?.configured ? "text-emerald-400 font-bold" : "text-red-400 font-bold"}>
                    {eonStatus?.engine_status?.api?.configured ? "Povezana ✓" : "Nije povezana"}
                  </span>
                </div>
                <div className="flex justify-between items-center text-xs">
                  <span className="text-text-secondary">CDM Decryption:</span>
                  <span className={eonStatus?.engine_status?.cdm_ready ? "text-emerald-400 font-bold" : "text-red-400 font-bold"}>
                    {eonStatus?.engine_status?.cdm_ready ? "Učitan ✓" : "device.wvd nedostaje"}
                  </span>
                </div>
              </div>

              {eonMissing.length > 0 && (
                <p className="text-[10px] text-text-muted font-mono bg-black/20 p-2 rounded border border-white/[0.02] break-all">Missing: {eonMissing.join(", ")}</p>
              )}
              {eonOptionalMissing.length > 0 && (
                <p className="text-[10px] text-text-muted font-mono bg-black/20 p-2 rounded border border-white/[0.02] break-all">Optional: {eonOptionalMissing.join(", ")}</p>
              )}
            </div>
          )}
        </div>

        <div className="glass-panel p-6 rounded-xl border border-glass flex flex-col gap-4 glow-green-card glow-card-premium">
          <h3 className="font-extrabold text-base flex items-center gap-2 text-white border-b border-white/[0.04] pb-3">
            <Lock className="w-5 h-5 text-emerald-400" />
            EON Kredencijali
          </h3>
          <div>
            <label>Korisničko ime / email</label>
            <div className="password-wrapper">
              <User className="absolute left-4 text-text-muted w-4 h-4" />
              <input
                type="text"
                value={eonUsername}
                onChange={(e) => setEonUsername(e.target.value)}
                placeholder="sbb_user@email.com"
                className="input-premium pl-11"
                style={cssVars({"--focused-border": "#10b981", "--focused-glow": "rgba(16,185,129,0.25)"})}
              />
            </div>
          </div>
          <div>
            <label>Lozinka</label>
            <div className="password-wrapper">
              <Lock className="absolute left-4 text-text-muted w-4 h-4" />
              <input
                type={showEonPass ? "text" : "password"}
                value={eonPassword}
                onChange={(e) => setEonPassword(e.target.value)}
                placeholder="••••••••"
                className="input-premium pl-11 pr-10"
                style={cssVars({"--focused-border": "#10b981", "--focused-glow": "rgba(16,185,129,0.25)"})}
              />
              <button
                type="button"
                className="password-eye-btn"
                onClick={() => setShowEonPass(!showEonPass)}
              >
                {showEonPass ? (
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" viewBox="0 0 24 24">
                    <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24" />
                    <line x1="1" y1="1" x2="23" y2="23" />
                  </svg>
                ) : (
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" viewBox="0 0 24 24">
                    <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
                    <circle cx="12" cy="12" r="3" />
                  </svg>
                )}
              </button>
            </div>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div>
              <label>Device serial</label>
              <input
                type="text"
                value={eonSerial}
                onChange={(e) => setEonSerial(e.target.value)}
                placeholder="device-serial"
                className="input-premium font-mono text-xs"
                style={cssVars({"--focused-border": "#10b981", "--focused-glow": "rgba(16,185,129,0.25)"})}
              />
            </div>
            <div>
              <label>Device number</label>
              <input
                type="text"
                value={eonNumber}
                onChange={(e) => setEonNumber(e.target.value)}
                placeholder="device-number"
                className="input-premium font-mono text-xs"
                style={cssVars({"--focused-border": "#10b981", "--focused-glow": "rgba(16,185,129,0.25)"})}
              />
            </div>
          </div>
          <button
            onClick={() => submitLogin("eon", { username: eonUsername, password: eonPassword, serial: eonSerial, number: eonNumber })}
            disabled={!eonUsername || !eonPassword || !eonSerial || !eonNumber}
            className="btn btn-premium-primary text-xs w-full mt-1"
            style={cssVars({
              "--btn-grad-start": "#10b981",
              "--btn-grad-end": "#059669",
              "--btn-glow": "rgba(16,185,129,0.25)",
              "--btn-glow-hover": "rgba(16,185,129,0.45)"
            })}
          >
            Sačuvaj EON podatke
          </button>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <button
              onClick={loginEonApi}
              disabled={!eonUsername || !eonPassword || !eonSerial || !eonNumber}
              className="btn btn-premium-secondary text-xs"
            >
              API login token
            </button>
            <button
              onClick={refreshEonApiToken}
              className="btn btn-premium-secondary text-xs"
            >
              Osveži API token
            </button>
          </div>
          <p className="text-[10px] text-text-muted leading-relaxed">
            Ova dugmad koriste samo vaš lokalni eon_api.json šablon. Ako API nije popunjen, možete i dalje koristiti lokalne kataloge i direktne media URL-ove.
          </p>
        </div>

        <div className="glass-panel p-6 rounded-xl border border-glass flex flex-col gap-4 glow-green-card glow-card-premium">
          <h3 className="font-extrabold text-base flex items-center gap-2 text-white border-b border-white/[0.04] pb-3">
            <FileText className="w-5 h-5 text-emerald-400" />
            Lokalne datoteke
          </h3>
          <div className="flex flex-col gap-2">
            <span className={`badge flex items-center gap-1 bg-emerald-500/10 border-emerald-500/30 text-emerald-400 font-bold px-2 py-0.5 rounded text-[10px] w-max ${deviceWvdInfo?.found ? "badge-connected" : "badge-missing"}`}>
              {deviceWvdInfo?.found ? "✓ device.wvd pronađen" : "✗ device.wvd nije podešen"}
            </span>
            <input
              type="text"
              value={binariesPaths.device_wvd || ""}
              onChange={(e) => setBinariesPaths({ ...binariesPaths, device_wvd: e.target.value })}
              placeholder="D:\ProjektiApp\videodownloadservisi\device.wvd"
              className="font-mono text-xs input-premium"
              style={cssVars({"--focused-border": "#10b981", "--focused-glow": "rgba(16,185,129,0.25)"})}
            />
            <button onClick={handleSaveDeviceWvdPath} className="btn btn-premium-secondary text-xs w-full">
              Sačuvaj device.wvd
            </button>
          </div>
          <div className="border-t border-white/[0.04] pt-4 text-[10px] text-text-muted font-mono flex flex-col gap-1.5 leading-normal">
            <span>Katalog kanala: <span className="text-text-secondary select-all">{eonCatalogPath("eon_channels.json")}</span></span>
            <span>Katalog serija: <span className="text-text-secondary select-all">{eonCatalogPath("eon_series.json")}</span></span>
            <span>API šablon: <span className="text-text-secondary select-all">{eonCatalogPath("eon_api.json")}</span></span>
          </div>
          <button onClick={initEonCatalogs} className="btn btn-premium-secondary text-xs w-full">
            Napravi početne katalog fajlove
          </button>
        </div>

        {/* EON TV IPTV DVR Scheduler Card */}
        <div className="glass-panel p-6 rounded-xl border border-glass flex flex-col gap-4 glow-green-card glow-card-premium transition-all">
          <h3 className="font-extrabold text-base flex items-center gap-2 text-white border-b border-white/[0.04] pb-3">
            <Clock className="w-5 h-5 text-emerald-400" />
            Zakazana DVR Snimanja
          </h3>
          
          {scheduledTasks.length === 0 ? (
            <p className="text-xs text-text-secondary leading-relaxed">
              Nema zakazanih snimanja. Koristite EPG listu iznad ili ručnu formu da zakažete snimanje live TV kanala.
            </p>
          ) : (
            <div className="flex flex-col gap-2.5 max-h-64 overflow-y-auto pr-1">
              {scheduledTasks.map((task: ScheduledTask) => (
                <div key={task.id} className="p-3 rounded-lg border border-glass bg-white/[0.01] flex items-center justify-between gap-3 text-xs">
                  <div className="flex-1 min-w-0">
                    <p className="font-bold text-white truncate">{task.title}</p>
                    <p className="text-[10px] text-text-muted mt-0.5 font-mono truncate">{task.channel_name} • {task.duration} min</p>
                    <p className="text-[10px] text-emerald-400 mt-1 flex items-center gap-1 font-semibold">
                      <Clock className="w-3 h-3 animate-pulse" />
                      {new Date(task.start_time).toLocaleString("sr-RS", {
                        day: "2-digit",
                        month: "2-digit",
                        hour: "2-digit",
                        minute: "2-digit"
                      })}
                    </p>
                  </div>
                  <button
                    onClick={async () => {
                      try {
                        const res = await apiFetch(`/api/scheduler/cancel`, {
                          method: "POST",
                          headers: { "Content-Type": "application/json" },
                          body: JSON.stringify({ id: task.id })
                        });
                        if (res.ok) {
                          showToast("✓ Zakazano snimanje otkazano", "info");
                          fetchScheduledRecordings();
                        }
                      } catch (err) {
                        console.error("Failed to cancel scheduled recording:", err);
                      }
                    }}
                    className="text-text-muted hover:text-red-400 p-1.5 hover:bg-red-500/10 rounded transition-all flex-shrink-0"
                    title="Otkaži snimanje"
                  >
                    <X className="w-3.5 h-3.5" />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  </div>
  );
}
