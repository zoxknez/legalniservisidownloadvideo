import { ChevronDown, Globe, Sliders, Sparkles } from "lucide-react";
import { CustomSelect } from "../CustomSelect";
import type { SmartDetectData } from "../../types/app";

export interface YtdlpDownloadPanelProps {
  data: SmartDetectData;
  resolution: string;
  setResolution: (v: string) => void;
  subs: string;
  setSubs: (v: string) => void;
  audioOnly: boolean;
  setAudioOnly: (v: boolean) => void;
  useAria2: boolean;
  setUseAria2: (v: boolean) => void;
  ytdlpCookiesBrowser: string;
  setYtdlpCookiesBrowser: (v: string) => void;
  ytdlpImpersonate: boolean;
  setYtdlpImpersonate: (v: boolean) => void;
  ytdlpProxy: string;
  setYtdlpProxy: (v: string) => void;
  ytdlpGeoBypass: boolean;
  setYtdlpGeoBypass: (v: boolean) => void;
  ytdlpEmbedThumbnail: boolean;
  setYtdlpEmbedThumbnail: (v: boolean) => void;
  ytdlpEmbedMetadata: boolean;
  setYtdlpEmbedMetadata: (v: boolean) => void;
  ytdlpLimitRate: string;
  setYtdlpLimitRate: (v: string) => void;
  ytdlpHardsub: boolean;
  setYtdlpHardsub: (v: boolean) => void;
  ytdlpSponsorblockMode: string;
  setYtdlpSponsorblockMode: (v: string) => void;
  ytdlpSplitChapters: boolean;
  setYtdlpSplitChapters: (v: boolean) => void;
  ytdlpDownloadPlaylist: boolean;
  setYtdlpDownloadPlaylist: (v: boolean) => void;
  ytdlpPlaylistItems: string;
  setYtdlpPlaylistItems: (v: string) => void;
  ytdlpFormatSpec: string;
  setYtdlpFormatSpec: (v: string) => void;
  ytdlpExtractorArgs: string;
  setYtdlpExtractorArgs: (v: string) => void;
  ytdlpCookiesConfigured: boolean;
  ytdlpCookiesUploading: boolean;
  uploadYtdlpCookies: (file: File) => Promise<void>;
  clearYtdlpCookies: () => Promise<void>;
  subsOpen: boolean;
  setSubsOpen: (v: boolean) => void;
  hardsubInputId?: string;
}

export function YtdlpDownloadPanel({
  data,
  resolution,
  setResolution,
  subs,
  setSubs,
  audioOnly,
  setAudioOnly,
  useAria2,
  setUseAria2,
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
  subsOpen,
  setSubsOpen,
  hardsubInputId = "ytdlpHardsub-console",
}: YtdlpDownloadPanelProps) {
  const hasEpisodeChecklist = !!(data.episodes && data.episodes.length > 0);

  return (
    <div className="ytdlp-console-container">
                <div className="ytdlp-console-wrapper animate-fade-in">
                  {/* Grid 1: Parameters (Dropdowns & Text inputs) */}
                  <div className="ytdlp-console-section">
                    <div className="ytdlp-console-section-header">
                      <Sliders className="w-4 h-4 text-blue-400" />
                      <span>Parametri preuzimanja (yt-dlp)</span>
                    </div>
                    <div className="ytdlp-grid-inputs">
                      {/* Rezolucija */}
                      <div className="ytdlp-option-group">
                        <label>Rezolucija</label>
                        <CustomSelect
                          value={resolution}
                          options={data.available_resolutions && data.available_resolutions.length > 0 
                            ? data.available_resolutions 
                            : ["1080p (Full HD)", "720p (HD)", "480p (SD)"]
                          }
                          onChange={(val) => setResolution(val)}
                        />
                        <span className="ytdlp-option-help">Željena rezolucija video fajla.</span>
                      </div>

                      {/* SponsorBlock */}
                      <div className="ytdlp-option-group">
                        <label>Sponzorski segmenti (SponsorBlock)</label>
                        <CustomSelect
                          value={ytdlpSponsorblockMode === "remove" ? "Ukloni sponzore" : ytdlpSponsorblockMode === "mark" ? "Samo obeleži" : "Isključeno"}
                          options={["Ukloni sponzore", "Samo obeleži", "Isključeno"]}
                          onChange={(val) => {
                            if (val === "Ukloni sponzore") setYtdlpSponsorblockMode("remove");
                            else if (val === "Samo obeleži") setYtdlpSponsorblockMode("mark");
                            else setYtdlpSponsorblockMode("disabled");
                          }}
                        />
                        <span className="ytdlp-option-help">Uklanja ili obeležava sponzorisane segmente (YouTube).</span>
                      </div>

                      {/* Uvoz kolačića */}
                      <div className="ytdlp-option-group">
                        <label>Uvoz kolačića (Cookies)</label>
                        <CustomSelect
                          value={ytdlpCookiesBrowser ? (ytdlpCookiesBrowser.charAt(0).toUpperCase() + ytdlpCookiesBrowser.slice(1)) : "Bez uvoza"}
                          options={["Bez uvoza", "Chrome", "Edge", "Firefox", "Brave"]}
                          onChange={(val) => setYtdlpCookiesBrowser(val === "Bez uvoza" ? "" : val.toLowerCase())}
                        />
                        <span className="ytdlp-option-help">Uvozi aktivnu sesiju pretraživača za privatan sadržaj.</span>
                        <div className="mt-2 flex flex-wrap items-center gap-2">
                          <label className="text-[10px] font-bold text-text-secondary cursor-pointer">
                            <input
                              type="file"
                              accept=".txt,.cookies"
                              className="hidden"
                              disabled={ytdlpCookiesUploading}
                              onChange={e => {
                                const f = e.target.files?.[0];
                                if (f) void uploadYtdlpCookies(f);
                                e.target.value = "";
                              }}
                            />
                            <span className="px-2 py-1 rounded border border-white/10 bg-black/30 hover:bg-white/5">
                              {ytdlpCookiesUploading ? "Otpremanje..." : "Otpremi cookies.txt"}
                            </span>
                          </label>
                          {ytdlpCookiesConfigured && (
                            <>
                              <span className="text-[10px] font-bold text-emerald-400">Fajl kolačića aktivan</span>
                              <button
                                type="button"
                                onClick={() => void clearYtdlpCookies()}
                                className="text-[10px] font-bold text-text-muted hover:underline"
                              >
                                Ukloni
                              </button>
                            </>
                          )}
                        </div>
                      </div>

                      {/* Limit brzine */}
                      <div className="ytdlp-option-group">
                        <label>Limit brzine preuzimanja</label>
                        <input
                          type="text"
                          value={ytdlpLimitRate}
                          onChange={e => setYtdlpLimitRate(e.target.value)}
                          placeholder="npr. 50K ili 5M"
                          maxLength={20}
                          className="ytdlp-advanced-input"
                        />
                        <span className="ytdlp-option-help">Ograničava protok mreže (ostavi prazno za max brzinu).</span>
                      </div>

                      {/* Proksi URL */}
                      <div className="ytdlp-option-group">
                        <label>Proksi URL</label>
                        <input
                          type="text"
                          value={ytdlpProxy}
                          onChange={e => setYtdlpProxy(e.target.value)}
                          placeholder="npr. http://127.0.0.1:8080"
                          maxLength={300}
                          className="ytdlp-advanced-input"
                        />
                        <span className="ytdlp-option-help">Rutira saobraćaj kroz proksi server (http/socks5).</span>
                      </div>

                      {/* Opseg videa iz plejliste — skriveno kad postoji vizuelna checklista */}
                      {!hasEpisodeChecklist && (
                        <div className="ytdlp-option-group" style={{ opacity: ytdlpDownloadPlaylist ? 1 : 0.45 }}>
                          <label>Opseg stavki iz plejliste</label>
                          <input
                            type="text"
                            value={ytdlpPlaylistItems}
                            onChange={e => setYtdlpPlaylistItems(e.target.value)}
                            placeholder={ytdlpDownloadPlaylist ? "npr. 1-5, 10" : "Prvo uključi plejliste"}
                            disabled={!ytdlpDownloadPlaylist}
                            maxLength={100}
                            className="ytdlp-advanced-input"
                            style={{ cursor: ytdlpDownloadPlaylist ? "text" : "not-allowed" }}
                          />
                          <span className="ytdlp-option-help">Preuzima samo određene delove plejliste (npr. 1-3, 5).</span>
                        </div>
                      )}

                      <div className="ytdlp-option-group md:col-span-2">
                        <label>Napredni format (opciono)</label>
                        <input
                          type="text"
                          value={ytdlpFormatSpec}
                          onChange={e => setYtdlpFormatSpec(e.target.value)}
                          maxLength={512}
                          placeholder="npr. bestvideo+bestaudio/best — prazno = automatski"
                          className="ytdlp-advanced-input"
                        />
                        <span className="ytdlp-option-help">Zamenjuje automatski izbor rezolucije ako je popunjeno.</span>
                      </div>

                      <div className="ytdlp-option-group md:col-span-2">
                        <label>Extractor argumenti (opciono)</label>
                        <input
                          type="text"
                          value={ytdlpExtractorArgs}
                          onChange={e => setYtdlpExtractorArgs(e.target.value)}
                          maxLength={512}
                          placeholder="npr. youtube:player_client=tv"
                          className="ytdlp-advanced-input"
                        />
                        <span className="ytdlp-option-help">Direktno prosleđuje --extractor-args yt-dlp komandi.</span>
                      </div>
                    </div>
                  </div>

                  {/* Grid 2: Additional Toggles (Checkbox Cards) */}
                  <div className="ytdlp-console-section">
                    <div className="ytdlp-console-section-header">
                      <Sliders className="w-4 h-4 text-blue-400" />
                      <span>Dodatne opcije i funkcije preuzimanja</span>
                    </div>
                    
                    <div className="ytdlp-grid-checkboxes">
                      {/* Preuzmi samo audio */}
                      <button
                        type="button"
                        className={`ytdlp-checkbox-card ${audioOnly ? "active" : ""}`}
                        onClick={() => setAudioOnly(!audioOnly)}
                      >
                        <div className="flex items-start gap-3 w-full">
                          <div className={`custom-checkbox-box ${audioOnly ? "checked" : ""}`} style={audioOnly ? {background:"#3b82f6", borderColor:"#3b82f6"} : {}}>
                            <svg className="custom-checkbox-check" viewBox="0 0 10 10" fill="none" stroke="white" strokeWidth="2">
                              <polyline points="1.5 5 4 7.5 8.5 2" />
                            </svg>
                          </div>
                          <div className="flex flex-col gap-0.5">
                            <span className="text-xs font-extrabold text-white">Preuzmi samo audio (MP3)</span>
                            <span className="text-[10px] text-text-secondary leading-normal">Ekstrahuje samo zvučni zapis i konvertuje ga u visokokvalitetni MP3.</span>
                          </div>
                        </div>
                      </button>

                      {/* Aria2 Ubrzanje */}
                      <button
                        type="button"
                        className={`ytdlp-checkbox-card ${useAria2 ? "active" : ""}`}
                        onClick={() => setUseAria2(!useAria2)}
                      >
                        <div className="flex items-start gap-3 w-full">
                          <div className={`custom-checkbox-box ${useAria2 ? "checked" : ""}`} style={useAria2 ? {background:"#3b82f6", borderColor:"#3b82f6"} : {}}>
                            <svg className="custom-checkbox-check" viewBox="0 0 10 10" fill="none" stroke="white" strokeWidth="2">
                              <polyline points="1.5 5 4 7.5 8.5 2" />
                            </svg>
                          </div>
                          <div className="flex flex-col gap-0.5">
                            <span className="text-xs font-extrabold text-white flex items-center gap-1">Aria2 ubrzanje <Sparkles className="w-3 h-3 text-amber-400 animate-pulse" /></span>
                            <span className="text-[10px] text-text-secondary leading-normal">Koristi spoljni download engine za multi-threaded preuzimanje.</span>
                          </div>
                        </div>
                      </button>

                      {/* Browser Impersonation */}
                      <button
                        type="button"
                        className={`ytdlp-checkbox-card ${ytdlpImpersonate ? "active" : ""}`}
                        onClick={() => setYtdlpImpersonate(!ytdlpImpersonate)}
                      >
                        <div className="flex items-start gap-3 w-full">
                          <div className={`custom-checkbox-box ${ytdlpImpersonate ? "checked" : ""}`} style={ytdlpImpersonate ? {background:"#3b82f6", borderColor:"#3b82f6"} : {}}>
                            <svg className="custom-checkbox-check" viewBox="0 0 10 10" fill="none" stroke="white" strokeWidth="2">
                              <polyline points="1.5 5 4 7.5 8.5 2" />
                            </svg>
                          </div>
                          <div className="flex flex-col gap-0.5">
                            <span className="text-xs font-extrabold text-white">Imitacija Chrome pretraživača</span>
                            <span className="text-[10px] text-text-secondary leading-normal">Imitira mrežni otisak Chrome-a radi zaobilaženja bot-zaštite.</span>
                          </div>
                        </div>
                      </button>

                      {/* Geo Bypass */}
                      <button
                        type="button"
                        className={`ytdlp-checkbox-card ${ytdlpGeoBypass ? "active" : ""}`}
                        onClick={() => setYtdlpGeoBypass(!ytdlpGeoBypass)}
                      >
                        <div className="flex items-start gap-3 w-full">
                          <div className={`custom-checkbox-box ${ytdlpGeoBypass ? "checked" : ""}`} style={ytdlpGeoBypass ? {background:"#3b82f6", borderColor:"#3b82f6"} : {}}>
                            <svg className="custom-checkbox-check" viewBox="0 0 10 10" fill="none" stroke="white" strokeWidth="2">
                              <polyline points="1.5 5 4 7.5 8.5 2" />
                            </svg>
                          </div>
                          <div className="flex flex-col gap-0.5">
                            <span className="text-xs font-extrabold text-white">Zaobilaženje geo-blokade</span>
                            <span className="text-[10px] text-text-secondary leading-normal">Šalje lažna geo-lokacijska zaglavlja kako bi se premostile regionalne blokade.</span>
                          </div>
                        </div>
                      </button>

                      {/* Ugradi sličicu */}
                      <button
                        type="button"
                        className={`ytdlp-checkbox-card ${ytdlpEmbedThumbnail ? "active" : ""}`}
                        onClick={() => setYtdlpEmbedThumbnail(!ytdlpEmbedThumbnail)}
                      >
                        <div className="flex items-start gap-3 w-full">
                          <div className={`custom-checkbox-box ${ytdlpEmbedThumbnail ? "checked" : ""}`} style={ytdlpEmbedThumbnail ? {background:"#3b82f6", borderColor:"#3b82f6"} : {}}>
                            <svg className="custom-checkbox-check" viewBox="0 0 10 10" fill="none" stroke="white" strokeWidth="2">
                              <polyline points="1.5 5 4 7.5 8.5 2" />
                            </svg>
                          </div>
                          <div className="flex flex-col gap-0.5">
                            <span className="text-xs font-extrabold text-white">Ugradi sličicu (Thumbnail) u video</span>
                            <span className="text-[10px] text-text-secondary leading-normal">Čuva naslovnu sliku (poster) direktno kao omot (artwork) unutar preuzetog fajla.</span>
                          </div>
                        </div>
                      </button>

                      {/* Ugradi metapodatke */}
                      <button
                        type="button"
                        className={`ytdlp-checkbox-card ${ytdlpEmbedMetadata ? "active" : ""}`}
                        onClick={() => setYtdlpEmbedMetadata(!ytdlpEmbedMetadata)}
                      >
                        <div className="flex items-start gap-3 w-full">
                          <div className={`custom-checkbox-box ${ytdlpEmbedMetadata ? "checked" : ""}`} style={ytdlpEmbedMetadata ? {background:"#3b82f6", borderColor:"#3b82f6"} : {}}>
                            <svg className="custom-checkbox-check" viewBox="0 0 10 10" fill="none" stroke="white" strokeWidth="2">
                              <polyline points="1.5 5 4 7.5 8.5 2" />
                            </svg>
                          </div>
                          <div className="flex flex-col gap-0.5">
                            <span className="text-xs font-extrabold text-white">Ugradi metapodatke i poglavlja</span>
                            <span className="text-[10px] text-text-secondary leading-normal">Zapisuje tagove (naslov, autor, opis) i vremenska poglavlja unutar kontejnera.</span>
                          </div>
                        </div>
                      </button>

                      {/* Podeli po poglavljima */}
                      <button
                        type="button"
                        className={`ytdlp-checkbox-card ${ytdlpSplitChapters ? "active" : ""}`}
                        onClick={() => setYtdlpSplitChapters(!ytdlpSplitChapters)}
                      >
                        <div className="flex items-start gap-3 w-full">
                          <div className={`custom-checkbox-box ${ytdlpSplitChapters ? "checked" : ""}`} style={ytdlpSplitChapters ? {background:"#3b82f6", borderColor:"#3b82f6"} : {}}>
                            <svg className="custom-checkbox-check" viewBox="0 0 10 10" fill="none" stroke="white" strokeWidth="2">
                              <polyline points="1.5 5 4 7.5 8.5 2" />
                            </svg>
                          </div>
                          <div className="flex flex-col gap-0.5">
                            <span className="text-xs font-extrabold text-white">Podeli video po poglavljima (Split)</span>
                            <span className="text-[10px] text-text-secondary leading-normal">Automatski seče i čuva svako poglavlje videa kao zaseban fajl.</span>
                          </div>
                        </div>
                      </button>

                      {/* Preuzmi celu plejlistu */}
                      <button
                        type="button"
                        className={`ytdlp-checkbox-card ${ytdlpDownloadPlaylist ? "active" : ""}`}
                        onClick={() => setYtdlpDownloadPlaylist(!ytdlpDownloadPlaylist)}
                      >
                        <div className="flex items-start gap-3 w-full">
                          <div className={`custom-checkbox-box ${ytdlpDownloadPlaylist ? "checked" : ""}`} style={ytdlpDownloadPlaylist ? {background:"#3b82f6", borderColor:"#3b82f6"} : {}}>
                            <svg className="custom-checkbox-check" viewBox="0 0 10 10" fill="none" stroke="white" strokeWidth="2">
                              <polyline points="1.5 5 4 7.5 8.5 2" />
                            </svg>
                          </div>
                          <div className="flex flex-col gap-0.5">
                            <span className="text-xs font-extrabold text-white">Preuzmi celu plejlistu</span>
                            <span className="text-[10px] text-text-secondary leading-normal">Omogućava preuzimanje svih snimaka iz plejliste ukoliko je unet link plejliste.</span>
                          </div>
                        </div>
                      </button>
                    </div>
                  </div>

                  {/* Subtitles & Translations (Collapsible Section Card) */}
                  <div className={`ytdlp-collapsible-card ${subsOpen ? "expanded" : ""}`}>
                    <div 
                      className="ytdlp-collapsible-header"
                      onClick={() => setSubsOpen(!subsOpen)}
                    >
                      <div className="flex items-center gap-2.5">
                        <Globe className="w-4 h-4 text-blue-400" />
                        <span className="text-xs font-extrabold text-white uppercase tracking-wider">Titlovi i prevodi</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="text-[10px] text-blue-400 font-bold bg-blue-500/10 px-2 py-0.5 rounded border border-blue-500/20">
                          {subs.trim() ? `Aktivno: ${subs}` : "Isključeno"}
                        </span>
                        <ChevronDown className={`w-4 h-4 text-text-secondary transition-transform duration-300 ${subsOpen ? "rotate-180" : ""}`} />
                      </div>
                    </div>

                    {subsOpen && (
                      <div className="ytdlp-collapsible-content animate-slide-down">
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-3 border-t border-white/[0.04]">
                          {/* Left sub-column: Text input */}
                          <div className="flex flex-col gap-2">
                            <label className="text-[10px] font-bold text-text-secondary uppercase">Jezici (odvojeni zarezom)</label>
                            <input
                              type="text"
                              value={subs}
                              onChange={e => setSubs(e.target.value)}
                              maxLength={120}
                              placeholder="npr. en,sr,hr ili all"
                              className="ytdlp-advanced-input w-full"
                            />
                            <span className="text-[10px] text-text-muted">Unesite dvoslovne oznake jezika ili "all" za sve dostupne prevode.</span>
                          </div>

                          {/* Right sub-column: Hardsub checkbox */}
                          <div className="flex items-center gap-3 bg-black/20 p-3 rounded-lg border border-white/[0.04] self-start">
                            <input
                              id={hardsubInputId}
                              type="checkbox"
                              checked={ytdlpHardsub}
                              disabled={!subs.trim()}
                              onChange={e => setYtdlpHardsub(e.target.checked)}
                              className="w-4 h-4 rounded text-blue-500 bg-black/40 border-glass cursor-pointer focus:ring-blue-500"
                            />
                            <div className="flex flex-col">
                              <label htmlFor={hardsubInputId} className="text-xs font-bold text-white cursor-pointer select-none">
                                Ugradi titlove u sliku (hardsub)
                              </label>
                              <span className="text-[10px] text-text-secondary">
                                Trajno ugrađuje titlove (SRT) u video pomoću FFmpeg-a. Potreban je bar jedan izabrani jezik.
                              </span>
                            </div>
                          </div>
                        </div>

                        {/* Manual Subtitles */}
                        {data.available_subtitles && data.available_subtitles.length > 0 && (
                          <div className="flex flex-col gap-2 mt-4">
                            <div className="text-[10px] text-text-muted font-bold uppercase tracking-wider">Detektovani prevodi (izvor):</div>
                            <div className="flex flex-wrap gap-1.5 max-h-32 overflow-y-auto pr-1">
                              {data.available_subtitles.map((lang: string) => {
                                const isSel = subs.split(",").map(s => s.trim().toLowerCase()).includes(lang.toLowerCase());
                                const toggleLang = (lang: string) => {
                                  const activeList = subs ? subs.split(",").map((s: string) => s.trim().toLowerCase()).filter(Boolean) : [];
                                  const l = lang.toLowerCase();
                                  if (activeList.includes(l)) {
                                    setSubs(activeList.filter((s: string) => s !== l).join(","));
                                  } else {
                                    setSubs([...activeList, l].join(","));
                                  }
                                };
                                return (
                                  <button
                                    key={lang}
                                    onClick={() => toggleLang(lang)}
                                    className={`px-2.5 py-1 rounded text-[10px] font-bold border transition-all ${
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
                        {data.available_auto_subtitles && data.available_auto_subtitles.length > 0 && (
                          <div className="flex flex-col gap-2 mt-4">
                            <div className="text-[10px] text-text-muted font-bold uppercase tracking-wider">Automatski (AI generisani):</div>
                            <div className="flex flex-wrap gap-1.5 max-h-32 overflow-y-auto pr-1">
                              {data.available_auto_subtitles.map((lang: string) => {
                                const isSel = subs.split(",").map(s => s.trim().toLowerCase()).includes(lang.toLowerCase());
                                const toggleLang = (lang: string) => {
                                  const activeList = subs ? subs.split(",").map((s: string) => s.trim().toLowerCase()).filter(Boolean) : [];
                                  const l = lang.toLowerCase();
                                  if (activeList.includes(l)) {
                                    setSubs(activeList.filter((s: string) => s !== l).join(","));
                                  } else {
                                    setSubs([...activeList, l].join(","));
                                  }
                                };
                                return (
                                  <button
                                    key={lang}
                                    onClick={() => toggleLang(lang)}
                                    className={`px-2.5 py-1 rounded text-[10px] font-bold border transition-all ${
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

                        <div className="flex gap-4 mt-3 border-t border-white/[0.03] pt-2.5 justify-end">
                          <button onClick={() => setSubs("all")} className="text-[10px] font-extrabold text-blue-400 hover:underline bg-none border-none cursor-pointer">
                            Uključi sve ("all")
                          </button>
                          <span className="text-white/[0.08] text-[10px]">|</span>
                          <button onClick={() => setSubs("")} className="text-[10px] font-extrabold text-text-muted hover:underline bg-none border-none cursor-pointer">
                            Isključi sve prevode
                          </button>
                        </div>
                      </div>
                    )}
                  </div>
                </div>
    </div>
  );
}
