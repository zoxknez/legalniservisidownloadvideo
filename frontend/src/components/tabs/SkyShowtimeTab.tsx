import { useState } from "react";
import {
  Check,
  ChevronDown,
  ChevronRight,
  Clipboard,
  Download,
  FileText,
  Globe,
  HardDrive,
  Info,
  KeyRound,
  Loader2,
  Lock,
  RefreshCw,
  Search,
  ShieldAlert,
  User,
  Video,
  X,
} from "lucide-react";
import { CustomSelect } from "../CustomSelect";
import { useSkyshowtimeTab } from "../../hooks/domains/useSkyshowtimeTab";
import type { SkyShowtimeEpisode, SkyShowtimeSeason } from "../../types/app";
import { cssVars } from "../../utils/cssVars";

function SkySeasonList({
  seriesData,
  selectedEpisodes,
  setSelectedEpisodes,
}: {
  seriesData: { title: string; description: string; seasons?: SkyShowtimeSeason[]; episodes: SkyShowtimeEpisode[] };
  selectedEpisodes: string[];
  setSelectedEpisodes: (ids: string[]) => void;
}) {
  const seasons = seriesData.seasons ?? [];
  const hasSeason = seasons.length > 0;
  const [expandedSeasons, setExpandedSeasons] = useState<Set<number>>(() => new Set(seasons.map((s) => s.season)));

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

  const toggleAllSeason = (eps: SkyShowtimeEpisode[]) => {
    const ids = eps.map((e) => e.id);
    const allChecked = ids.every((id) => selectedEpisodes.includes(id));
    if (allChecked) {
      setSelectedEpisodes(selectedEpisodes.filter((id) => !ids.includes(id)));
    } else {
      setSelectedEpisodes([...new Set([...selectedEpisodes, ...ids])]);
    }
  };

  const renderEpisode = (ep: SkyShowtimeEpisode) => {
    const checked = selectedEpisodes.includes(ep.id);
    return (
      <div
        key={ep.id}
        className="custom-checkbox-wrap"
        style={cssVars({ borderRadius: 8, padding: "8px 10px", "--checkbox-bg": "#14b8a6", "--checkbox-glow": "rgba(20, 184, 166, 0.3)" })}
        onClick={() => toggleEp(ep.id)}
      >
        <div className={`custom-checkbox-box ${checked ? "checked" : ""}`}>
          <svg className="custom-checkbox-check" viewBox="0 0 10 10" fill="none" stroke="white" strokeWidth="2"><polyline points="1.5 5 4 7.5 8.5 2" /></svg>
        </div>
        <span className="font-extrabold text-[10px] tracking-wider uppercase bg-teal-500/10 text-teal-300 border border-teal-500/20 px-2 py-0.5 rounded min-w-16 text-center">
          S{ep.season.toString().padStart(2, "0")}E{ep.episode.toString().padStart(2, "0")}
        </span>
        <span className="flex-1 truncate text-white text-sm font-semibold">{ep.title}</span>
        {ep.length_mins > 0 && <span className="text-xs text-text-muted">{ep.length_mins}m</span>}
        {ep.drm && <span title="DRM"><Lock className="w-3.5 h-3.5 text-amber-500" /></span>}
      </div>
    );
  };

  return (
    <div className="border-t border-glass pt-6 flex flex-col gap-4">
      <div>
        <h3 className="font-extrabold text-lg text-teal-400">{seriesData.title}</h3>
        <p className="text-xs text-text-secondary mt-1">{seriesData.description}</p>
      </div>
      <div className="flex justify-between items-center">
        <label className="m-0 font-bold text-xs">
          {hasSeason ? `${seasons.length} sezona — ${seriesData.episodes.length} epizoda` : `${seriesData.episodes.length} epizoda`}
        </label>
        <div className="flex gap-2">
          <button type="button" className="text-[10px] uppercase font-extrabold text-teal-400 bg-teal-500/5 hover:bg-teal-500/15 border border-teal-500/10 px-2 py-1 rounded" onClick={() => setSelectedEpisodes(seriesData.episodes.map((e) => e.id))}>
            <Check className="w-3 h-3 inline" /> Označi sve
          </button>
          <button type="button" className="text-[10px] uppercase font-extrabold text-text-muted bg-white/[0.02] border border-white/[0.05] px-2 py-1 rounded" onClick={() => setSelectedEpisodes([])}>
            <X className="w-3 h-3 inline" /> Odznači
          </button>
        </div>
      </div>
      <div className="max-h-80 overflow-y-auto border border-glass rounded-lg bg-black/40 p-2 flex flex-col gap-1">
        {hasSeason ? seasons.map((season) => {
          const isOpen = expandedSeasons.has(season.season);
          const seasonEps = season.episodes;
          const checkedCount = seasonEps.filter((e) => selectedEpisodes.includes(e.id)).length;
          const allChecked = checkedCount === seasonEps.length;
          return (
            <div key={season.season}>
              <div className="flex items-center gap-2 px-2 py-2 rounded-lg cursor-pointer hover:bg-white/[0.04]" onClick={() => toggleSeason(season.season)}>
                {isOpen ? <ChevronDown className="w-4 h-4 text-teal-400" /> : <ChevronRight className="w-4 h-4 text-text-muted" />}
                <span className="font-extrabold text-sm text-white flex-1">Sezona {season.season}</span>
                <span className="text-[10px] text-text-muted">{checkedCount}/{seasonEps.length}</span>
                <button type="button" className={`text-[10px] uppercase font-extrabold px-2 py-0.5 rounded ${allChecked ? "text-text-muted" : "text-teal-400 bg-teal-500/10 border border-teal-500/20"}`} onClick={(e) => { e.stopPropagation(); toggleAllSeason(seasonEps); }}>
                  {allChecked ? "Odznači" : "Označi"}
                </button>
              </div>
              {isOpen && <div className="flex flex-col gap-1 ml-4 mb-2">{seasonEps.map(renderEpisode)}</div>}
            </div>
          );
        }) : seriesData.episodes.map(renderEpisode)}
      </div>
    </div>
  );
}

export function SkyShowtimeTab() {
  const {
    skyshowtimeTarget,
    setSkyshowtimeTarget,
    skyshowtimeSeason,
    setSkyshowtimeSeason,
    skyshowtimeStartEp,
    setSkyshowtimeStartEp,
    skyshowtimeEndEp,
    setSkyshowtimeEndEp,
    skyshowtimeVcodec,
    setSkyshowtimeVcodec,
    skyshowtimeQuality,
    setSkyshowtimeQuality,
    skyshowtimeAudioLang,
    setSkyshowtimeAudioLang,
    skyshowtimeSubmitting,
    skyshowtimeAuth,
    refreshAuth,
    startSkyshowtimeBrowserSync,
    startSkyshowtimeLogin,
    skyshowtimeDirectMode,
    setSkyshowtimeDirectMode,
    skyshowtimeManifestUrl,
    setSkyshowtimeManifestUrl,
    skyshowtimeLicenseUrl,
    setSkyshowtimeLicenseUrl,
    skyshowtimeLicenseToken,
    setSkyshowtimeLicenseToken,
    skyshowtimeDirectTitle,
    setSkyshowtimeDirectTitle,
    skyshowtimeSeriesData,
    setSkyshowtimeSeriesData,
    selectedSkyshowtimeEpisodes,
    setSelectedSkyshowtimeEpisodes,
    skyshowtimeSearching,
    searchSkyshowtimeSeries,
    startSkyshowtimeDownload,
    startSkyshowtimeDirectDownload,
    pasteSkyshowtimeTarget,
    status,
  } = useSkyshowtimeTab();

  const [cookieText, setCookieText] = useState("");
  const [authTab, setAuthTab] = useState<"sync" | "paste">("sync");
  const [showAdvancedEp, setShowAdvancedEp] = useState(false);

  const isAuthenticated =
    skyshowtimeAuth?.authenticated ?? status?.services?.skyshowtime?.authenticated ?? false;
  const isCdmReady = status?.binaries?.device_wvd?.found ?? false;
  const canDownload = isAuthenticated && isCdmReady && !skyshowtimeSubmitting;

  const handleManualCookieImport = () => {
    if (!cookieText.trim()) return;
    startSkyshowtimeLogin(cookieText.trim());
    setCookieText("");
  };

  const handleBrowserSync = () => {
    startSkyshowtimeBrowserSync();
  };

  return (
    <div key="skyshowtime" className="tab-content tab-content-skyshowtime">
      <div className="tab-page-header tab-header-skyshowtime mb-6">
        <div className="tab-page-header-icon" style={{ background: "linear-gradient(135deg, #06b6d4, #0891b2)" }}>
          <Video style={{ width: 24, height: 24, color: "white" }} />
        </div>
        <div style={{ flex: 1 }}>
          <div className="flex items-center justify-between flex-wrap gap-2">
            <h2 className="text-2xl font-extrabold text-white mb-1 flex items-center gap-2.5">
              <Video className="w-6 h-6 text-cyan-400" /> SkyShowtime
            </h2>
            <span className="badge flex items-center gap-1.5 bg-cyan-500/10 border-cyan-500/30 text-cyan-400 font-black px-2.5 py-1 text-[10px] tracking-wider rounded-md">
              <Lock className="w-3.5 h-3.5" /> WIDEVINE L3 DEKRIPCIJA
            </span>
          </div>
          <p className="text-text-secondary text-sm">
            Preuzimanje filmova i serija, pregled epizoda po sezonama, ili Bypass Mode sa direktnim MPD/License URL-ovima (sniffer).
          </p>
        </div>
      </div>

      <div className="sliding-tabs-wrapper mb-2">
        <div
          className="sliding-tabs-slider"
          style={{
            width: "calc(50% - 4px)",
            transform: `translateX(${!skyshowtimeDirectMode ? "0%" : "100%"})`,
          }}
        />
        <button type="button" onClick={() => setSkyshowtimeDirectMode(false)} className={`sliding-tabs-btn ${!skyshowtimeDirectMode ? "active" : ""}`}>
          Standardno (URL / Serija)
        </button>
        <button type="button" onClick={() => setSkyshowtimeDirectMode(true)} className={`sliding-tabs-btn ${skyshowtimeDirectMode ? "active" : ""}`}>
          Bypass Mode (Direct URL)
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
        <div className="md:col-span-2 flex flex-col gap-6">
          
          {/* Authentication Section */}
          <div className="glass-panel p-8 rounded-xl border border-glass flex flex-col gap-6 glow-cyan-card glow-card-premium">
            <h3 className="font-extrabold text-lg text-white flex items-center gap-2">
              <KeyRound className="w-5 h-5 text-cyan-400" />
              Prijava na SkyShowtime
            </h3>

            {/* Auth Mode Toggle */}
            <div className="sliding-tabs-wrapper mb-2">
              <div
                className="sliding-tabs-slider"
                style={{
                  width: "calc(50% - 4px)",
                  transform: `translateX(${authTab === "sync" ? "0%" : "100%"})`
                }}
              />
              <button
                type="button"
                onClick={() => setAuthTab("sync")}
                className={`sliding-tabs-btn ${authTab === "sync" ? "active" : ""}`}
              >
                Auto-sinhronizacija pretraživača
              </button>
              <button
                type="button"
                onClick={() => setAuthTab("paste")}
                className={`sliding-tabs-btn ${authTab === "paste" ? "active" : ""}`}
              >
                Ručni uvoz (cookies.txt)
              </button>
            </div>

            {authTab === "sync" ? (
              <div className="flex flex-col gap-4">
                <p className="text-xs text-text-secondary leading-relaxed">
                  Najlakši način: ulogujte se na <a href="https://www.skyshowtime.com" target="_blank" rel="noreferrer" className="text-cyan-400 underline">skyshowtime.com</a> u vašem Google Chrome, Edge ili Brave pretraživaču. Zatim kliknite na dugme ispod da preuzmete sesiju automatski.
                </p>
                <button
                  onClick={handleBrowserSync}
                  disabled={skyshowtimeSubmitting}
                  className="btn btn-premium-secondary py-3 px-6 text-white font-bold"
                  style={cssVars({
                    "--btn-glow": "rgba(6,182,212,0.15)"
                  })}
                >
                  <RefreshCw className={`w-4 h-4 ${skyshowtimeSubmitting ? "animate-spin" : ""}`} />
                  Sinhronizuj sesiju iz pretraživača
                </button>
              </div>
            ) : (
              <div className="flex flex-col gap-4">
                <p className="text-xs text-text-secondary leading-relaxed">
                  Zalepite kompletan sadržaj Netscape <code className="font-mono bg-white/10 px-1 rounded">cookies.txt</code> fajla izvezenog pomoću ekstenzije poput "Get cookies.txt LOCALLY".
                </p>
                <textarea
                  placeholder="# Netscape HTTP Cookie File..."
                  rows={4}
                  value={cookieText}
                  onChange={(e) => setCookieText(e.target.value)}
                  className="input-premium font-mono text-xs p-3 min-h-[100px]"
                  style={cssVars({ "--focused-border": "#06b6d4", "--focused-glow": "rgba(6,182,212,0.25)" })}
                />
                <button
                  onClick={handleManualCookieImport}
                  disabled={!cookieText.trim() || skyshowtimeSubmitting}
                  className="btn btn-premium-secondary py-3 px-6 text-white font-bold"
                >
                  <FileText className="w-4 h-4" />
                  Uvezi kolačiće (Cookies)
                </button>
              </div>
            )}
          </div>

          {/* Download Form */}
          <div className="glass-panel p-8 rounded-xl border border-glass flex flex-col gap-6 glow-cyan-card glow-card-premium">
            <h3 className="font-extrabold text-lg text-white flex items-center gap-2">
              <Download className="w-5 h-5 text-cyan-400" />
              {skyshowtimeDirectMode ? "Bypass Preuzimanje" : "Preuzimanje Videa"}
            </h3>

            {!skyshowtimeDirectMode ? (
            <>
            <div>
              <label>Video URL</label>
              <div className="password-wrapper">
                <Video className="absolute left-4 text-text-muted w-4 h-4" />
                <input
                  type="text"
                  placeholder="https://www.skyshowtime.com/watch/asset/movies/naziv/ID ili /tv/naziv/ID"
                  value={skyshowtimeTarget}
                  onChange={(e) => {
                    setSkyshowtimeTarget(e.target.value);
                    setSkyshowtimeSeriesData(null);
                    setSelectedSkyshowtimeEpisodes([]);
                  }}
                  onKeyDown={(e) => e.key === "Enter" && !skyshowtimeSearching && skyshowtimeTarget.trim() && searchSkyshowtimeSeries()}
                  className="input-premium pl-11 pr-24"
                  style={cssVars({ "--focused-border": "#06b6d4", "--focused-glow": "rgba(6,182,212,0.25)" })}
                />
                <button type="button" className="absolute right-12 top-1/2 -translate-y-1/2 text-text-muted hover:text-cyan-400 p-1 rounded" title="Nalepi" onClick={pasteSkyshowtimeTarget}>
                  <Clipboard className="w-4 h-4" />
                </button>
                <button
                  type="button"
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-teal-400 hover:text-teal-300 p-1 rounded"
                  title="Pretraži seriju"
                  disabled={!skyshowtimeTarget.trim() || skyshowtimeSearching}
                  onClick={searchSkyshowtimeSeries}
                >
                  {skyshowtimeSearching ? <Loader2 className="w-4 h-4 animate-spin" /> : <Search className="w-4 h-4" />}
                </button>
              </div>
              <p className="text-[10px] text-text-muted mt-1.5">
                Za serije kliknite lupu da učitate epizode. Filmovi se preuzimaju direktno.
              </p>
            </div>

            {skyshowtimeSeriesData && (
              <SkySeasonList
                seriesData={skyshowtimeSeriesData}
                selectedEpisodes={selectedSkyshowtimeEpisodes}
                setSelectedEpisodes={setSelectedSkyshowtimeEpisodes}
              />
            )}

            {!skyshowtimeSeriesData && (
            <>
            {/* Checkbox for advanced episode configuration */}
            <div className="flex items-center gap-3">
              <div className="custom-checkbox-wrap cursor-pointer" onClick={() => setShowAdvancedEp(!showAdvancedEp)}>
                <div className={`custom-checkbox-box ${showAdvancedEp ? "checked" : ""}`} style={cssVars({ "--checkbox-bg": "#06b6d4", "--checkbox-glow": "rgba(6,182,212,0.3)" })}>
                  <svg className="custom-checkbox-check" viewBox="0 0 10 10" fill="none" stroke="white" strokeWidth="2"><polyline points="1.5 5 4 7.5 8.5 2" /></svg>
                </div>
                <span className="text-xs text-text-secondary font-semibold select-none">
                  Filtriraj po sezoni / epizodama (samo za serije)
                </span>
              </div>
            </div>

            {showAdvancedEp && (
              <div className="grid grid-cols-3 gap-4 p-4 rounded-lg bg-white/[0.02] border border-white/[0.04]">
                <div>
                  <label>Broj sezone</label>
                  <input
                    type="number"
                    min={1}
                    placeholder="Sve sezone"
                    value={skyshowtimeSeason}
                    onChange={(e) => setSkyshowtimeSeason(e.target.value)}
                    className="input-premium"
                    style={cssVars({ "--focused-border": "#06b6d4", "--focused-glow": "rgba(6,182,212,0.25)" })}
                  />
                </div>
                <div>
                  <label>Početna epizoda</label>
                  <input
                    type="number"
                    min={1}
                    value={skyshowtimeStartEp}
                    onChange={(e) => setSkyshowtimeStartEp(e.target.value)}
                    className="input-premium"
                    style={cssVars({ "--focused-border": "#06b6d4", "--focused-glow": "rgba(6,182,212,0.25)" })}
                  />
                </div>
                <div>
                  <label>Završna epizoda</label>
                  <input
                    type="number"
                    min={1}
                    placeholder="Do kraja sezone"
                    value={skyshowtimeEndEp}
                    onChange={(e) => setSkyshowtimeEndEp(e.target.value)}
                    className="input-premium"
                    style={cssVars({ "--focused-border": "#06b6d4", "--focused-glow": "rgba(6,182,212,0.25)" })}
                  />
                </div>
              </div>
            )}
            </>
            )}

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label>Video Kodek</label>
                <CustomSelect
                  value={skyshowtimeVcodec}
                  options={["H264", "H265"]}
                  onChange={(val) => setSkyshowtimeVcodec(val)}
                  formatLabel={(val) => val === "H264" ? "H.264 (Default)" : "H.265 (HEVC)"}
                />
              </div>
              <div>
                <label>Kvalitet / Boje</label>
                <CustomSelect
                  value={skyshowtimeQuality}
                  options={["SDR", "HDR10", "DV"]}
                  onChange={(val) => setSkyshowtimeQuality(val)}
                  formatLabel={(val) =>
                    val === "SDR" ? "SDR (Standardno)" :
                    val === "HDR10" ? "HDR10" :
                    "Dolby Vision"
                  }
                />
              </div>
            </div>

            <div>
              <label>Audio jezik</label>
              <CustomSelect
                value={skyshowtimeAudioLang}
                options={["en", "sr", "hr", "sl"]}
                onChange={(val) => setSkyshowtimeAudioLang(val)}
                formatLabel={(val) =>
                  val === "en" ? "Engleski (podrazumevano)" :
                  val === "sr" ? "Srpski" :
                  val === "hr" ? "Hrvatski" :
                  "Slovenački"
                }
              />
            </div>

            {!isAuthenticated && (
              <p className="text-xs text-amber-400/90">
                Preuzimanje zahteva aktivnu sesiju — prvo sinhronizujte pretraživač ili uvezite kolačiće.
              </p>
            )}
            {!isCdmReady && (
              <p className="text-xs text-amber-400/90">
                Nedostaje <code className="font-mono bg-white/[0.04] px-1 rounded">device.wvd</code> u root folderu aplikacije.
              </p>
            )}

            <button
              onClick={startSkyshowtimeDownload}
              disabled={
                !skyshowtimeTarget.trim() || !canDownload ||
                (skyshowtimeSeriesData != null && selectedSkyshowtimeEpisodes.length === 0)
              }
              className="btn btn-premium-primary w-full py-4 text-white font-bold"
              style={cssVars({
                "--btn-grad-start": "#06b6d4",
                "--btn-grad-end": "#0891b2",
                "--btn-glow": "rgba(6,182,212,0.25)",
                "--btn-glow-hover": "rgba(6,182,212,0.45)"
              })}
            >
              <Download className="w-5 h-5" />
              {skyshowtimeSubmitting ? "Slanje..." :
                skyshowtimeSeriesData && selectedSkyshowtimeEpisodes.length > 0
                  ? `Preuzmi ${selectedSkyshowtimeEpisodes.length} epizod${selectedSkyshowtimeEpisodes.length === 1 ? "u" : "e"}`
                  : "Započni Preuzimanje"}
            </button>
            </>
            ) : (
            <>
              <div>
                <label>MPD Manifest URL</label>
                <input type="text" placeholder="https://...manifest.mpd" value={skyshowtimeManifestUrl} onChange={(e) => setSkyshowtimeManifestUrl(e.target.value)} className="input-premium font-mono text-xs" style={cssVars({ "--focused-border": "#06b6d4" })} />
              </div>
              <div>
                <label>Widevine License URL</label>
                <input type="text" placeholder="https://.../widevine/..." value={skyshowtimeLicenseUrl} onChange={(e) => setSkyshowtimeLicenseUrl(e.target.value)} className="input-premium font-mono text-xs" style={cssVars({ "--focused-border": "#06b6d4" })} />
              </div>
              <div>
                <label>X-License-Token (opciono)</label>
                <input type="text" placeholder="Iz sniffera ili network taba" value={skyshowtimeLicenseToken} onChange={(e) => setSkyshowtimeLicenseToken(e.target.value)} className="input-premium font-mono text-xs" style={cssVars({ "--focused-border": "#06b6d4" })} />
              </div>
              <div>
                <label>Naslov fajla</label>
                <input type="text" placeholder="Opcioni naslov za MKV" value={skyshowtimeDirectTitle} onChange={(e) => setSkyshowtimeDirectTitle(e.target.value)} className="input-premium" style={cssVars({ "--focused-border": "#06b6d4" })} />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label>Video Kodek</label>
                  <CustomSelect
                    value={skyshowtimeVcodec}
                    options={["H264", "H265"]}
                    onChange={(val) => setSkyshowtimeVcodec(val)}
                    formatLabel={(val) => val === "H264" ? "H.264 (Default)" : "H.265 (HEVC)"}
                  />
                </div>
                <div>
                  <label>Kvalitet / Boje</label>
                  <CustomSelect
                    value={skyshowtimeQuality}
                    options={["SDR", "HDR10", "DV"]}
                    onChange={(val) => setSkyshowtimeQuality(val)}
                    formatLabel={(val) =>
                      val === "SDR" ? "SDR (Standardno)" :
                      val === "HDR10" ? "HDR10" :
                      "Dolby Vision"
                    }
                  />
                </div>
              </div>
              <div>
                <label>Audio jezik</label>
                <CustomSelect
                  value={skyshowtimeAudioLang}
                  options={["en", "sr", "hr", "sl"]}
                  onChange={(val) => setSkyshowtimeAudioLang(val)}
                  formatLabel={(val) =>
                    val === "en" ? "Engleski (podrazumevano)" :
                    val === "sr" ? "Srpski" :
                    val === "hr" ? "Hrvatski" :
                    "Slovenački"
                  }
                />
              </div>
              <button
                onClick={startSkyshowtimeDirectDownload}
                disabled={!skyshowtimeManifestUrl.trim() || !skyshowtimeLicenseUrl.trim() || !canDownload}
                className="btn btn-premium-primary w-full py-4 text-white font-bold"
                style={cssVars({ "--btn-grad-start": "#06b6d4", "--btn-grad-end": "#0891b2" })}
              >
                <Download className="w-5 h-5" />
                {skyshowtimeSubmitting ? "Slanje..." : "Preuzmi (Bypass)"}
              </button>
            </>
            )}
          </div>

        </div>

        {/* Sidebar Diagnostics */}
        <div className="flex flex-col gap-6">
          
          {/* Auth status card */}
          <div className="glass-panel p-6 rounded-xl border border-glass glow-cyan-card glow-card-premium">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-extrabold text-base flex items-center gap-2 text-white">
                <User className="w-5 h-5 text-cyan-400" />
                Status Sesije
              </h3>
              <button
                type="button"
                className="text-text-muted hover:text-cyan-400 transition-colors p-1 rounded"
                title="Osveži status"
                onClick={refreshAuth}
              >
                <RefreshCw className="w-3.5 h-3.5" />
              </button>
            </div>
            
            {isAuthenticated ? (
              <div className="flex flex-col gap-3">
                <span className="badge flex items-center gap-1.5 bg-emerald-500/10 border-emerald-500/30 text-emerald-400 font-black px-2.5 py-1 text-[10px] tracking-wider rounded-md w-max" style={cssVars({ animation: "pulseGlowBrighter 2s infinite", "--glow-color": "rgba(16, 185, 129, 0.2)" })}>
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 shadow-[0_0_8px_#34d399]"></span> AKTIVAN
                </span>
                <p className="text-xs text-text-secondary leading-relaxed">
                  SkyShowtime autentifikacioni token je uspešno učitan i važeći.
                </p>
                {skyshowtimeAuth?.token_expiry && (
                  <p className="text-[10px] text-text-muted mt-1">
                    Ističe: <span className="font-semibold text-white">{new Date(skyshowtimeAuth.token_expiry).toLocaleString("sr-RS")}</span>
                  </p>
                )}
                {skyshowtimeAuth?.token_path && (
                  <p className="text-[10px] text-text-muted break-all mt-1 font-mono bg-white/[0.03] px-2 py-1.5 rounded">
                    {skyshowtimeAuth.token_path}
                  </p>
                )}
              </div>
            ) : (
              <div className="flex flex-col gap-3">
                <span className="badge flex items-center gap-1.5 bg-red-500/10 border-red-500/30 text-red-400 font-black px-2.5 py-1 text-[10px] tracking-wider rounded-md w-max">
                  <span className="w-1.5 h-1.5 rounded-full bg-red-400 animate-ping"></span> NIJE PRIJAVLJEN
                </span>
                <p className="text-xs text-text-secondary leading-relaxed mt-1">
                  Nema validnog tokena. Sinhronizujte sesiju iz pretraživača ili uvezite cookies.txt.
                </p>
              </div>
            )}
            
            {skyshowtimeAuth?.territory && (
              <div className="mt-4 pt-4 border-t border-white/[0.04] flex items-center gap-2">
                <Globe className="w-4 h-4 text-text-muted" />
                <span className="text-xs text-text-secondary">Teritorija: <span className="font-bold text-white uppercase">{skyshowtimeAuth.territory}</span></span>
              </div>
            )}
          </div>

          {/* CDM Status Card */}
          <div className="glass-panel p-6 rounded-xl border border-glass glow-cyan-card glow-card-premium">
            <h3 className="font-extrabold text-base mb-3 flex items-center gap-2 text-white">
              <HardDrive className="w-5 h-5 text-cyan-400" />
              CDM Dekripcija
            </h3>
            {isCdmReady ? (
              <div className="flex flex-col gap-2">
                <span className="badge flex items-center gap-1.5 bg-emerald-500/10 border-emerald-500/30 text-emerald-400 font-black px-2 py-1 text-[10px] tracking-wider rounded-md w-max">
                  <Check className="w-3 h-3" /> CDM DOSTUPAN
                </span>
                <p className="text-[10px] text-text-muted break-all font-mono bg-white/[0.03] px-2 py-1.5 rounded mt-1">
                  {status?.binaries?.device_wvd?.path}
                </p>
              </div>
            ) : (
              <div className="flex flex-col gap-2">
                <span className="badge flex items-center gap-1.5 bg-amber-500/10 border-amber-500/30 text-amber-400 font-black px-2 py-1 text-[10px] tracking-wider rounded-md w-max">
                  <ShieldAlert className="w-3 h-3" /> CDM NEDOSTAJE
                </span>
                <p className="text-xs text-text-secondary leading-relaxed mt-1">
                  Za dešifrovanje SkyShowtime videa potreban je <code className="font-mono bg-white/[0.04] px-1 rounded text-cyan-300">device.wvd</code> fajl u root folderu aplikacije.
                </p>
              </div>
            )}
          </div>

          {/* Quick Guide */}
          <div className="glass-panel p-6 rounded-xl border border-glass flex flex-col gap-3 glow-cyan-card glow-card-premium">
            <h3 className="font-extrabold text-base mb-3 flex items-center gap-2 text-white border-b border-white/[0.04] pb-3">
              <Info className="w-5 h-5 text-cyan-400" />
              Uputstvo
            </h3>
            <ol className="text-xs text-text-secondary flex flex-col gap-2.5 list-none">
              <li className="flex gap-2">
                <span className="w-5 h-5 rounded-full bg-cyan-500/20 text-cyan-300 flex items-center justify-center flex-shrink-0 text-[10px] font-bold">1</span>
                <span>Prijavite se na skyshowtime.com u pretraživaču</span>
              </li>
              <li className="flex gap-2">
                <span className="w-5 h-5 rounded-full bg-cyan-500/20 text-cyan-300 flex items-center justify-center flex-shrink-0 text-[10px] font-bold">2</span>
                <span>Kliknite "Sinhronizuj sesiju iz pretraživača"</span>
              </li>
              <li className="flex gap-2">
                <span className="w-5 h-5 rounded-full bg-cyan-500/20 text-cyan-300 flex items-center justify-center flex-shrink-0 text-[10px] font-bold">3</span>
                <span>Zalepite link filma ili serije i pokrenite preuzimanje</span>
              </li>
            </ol>
          </div>

        </div>
      </div>
    </div>
  );
}
