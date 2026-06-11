import {
  Download,
  ExternalLink,
  Film,
  List,
  Loader2,
  Lock,
  Search,
  Settings,
  ShieldAlert,
  Tv,
  User,
} from "lucide-react";
import { CustomSelect } from "../CustomSelect";
import { VoyoSeasonList } from "../voyo/VoyoSeasonList";
import {
  VOYO_HINT_MSG,
  voyoCatalogDrmHint,
  voyoIsHardBlocked,
  voyoIsSoftHint,
} from "../../lib/voyoDrm";
import { useVoyoTab } from "../../hooks/domains/useVoyoTab";
import { useAppShellSlice } from "../../context/appStore";
import { cssVars } from "../../utils/cssVars";

const VARIANT_LABEL: Record<string, string> = {
  rs: "Srbija (voyo.rs)",
  hr: "Hrvatska (voyo.hr)",
};

export function VoyoTab() {
  const { setActiveTab } = useAppShellSlice();
  const {
    searchVoyoSeries,
    selectedVoyoEpisodes,
    setSelectedVoyoEpisodes,
    setVoyoMode,
    setVoyoRes,
    setVoyoSeriesData,
    setVoyoTarget,
    startVoyoDownload,
    status,
    voyoMode,
    voyoEpisodesRange,
    voyoRes,
    voyoSearching,
    voyoPreviewLoading,
    voyoSeriesData,
    voyoVideoPreview,
    voyoSubmitting,
    voyoTarget,
    setVoyoEpisodesRange,
    ignoreCatalogDrmHint,
  } = useVoyoTab();

  const voyoSvc = status?.services?.voyo;
  const variant = voyoSvc?.variant || "rs";
  const variantLabel = VARIANT_LABEL[variant] || variant.toUpperCase();

  const ctaDisabled =
    !voyoTarget.trim() ||
    voyoSubmitting ||
    (voyoMode === "series" && voyoSeriesData && selectedVoyoEpisodes.length === 0) ||
    (voyoMode === "video" && !!voyoVideoPreview && voyoIsHardBlocked(voyoVideoPreview));

  const ctaLabel =
    voyoSubmitting
      ? "Slanje..."
      : voyoMode === "series" && voyoSeriesData
        ? `Preuzmi ${selectedVoyoEpisodes.length} epizod${selectedVoyoEpisodes.length === 1 ? "u" : selectedVoyoEpisodes.length < 5 ? "e" : "a"}`
        : "Započni preuzimanje";

  return (
    <div key="voyo" className="tab-content tab-content-voyo">
      <div className="tab-page-header tab-header-voyo mb-8">
        <div className="tab-page-header-icon" style={{ background: "linear-gradient(135deg,#f97316,#ea580c)" }}>
          <Tv style={{ width: 24, height: 24, color: "white" }} />
        </div>
        <div style={{ flex: 1 }}>
          <div className="flex items-center justify-between flex-wrap gap-2">
            <h2 className="text-2xl font-extrabold text-white mb-1 flex items-center gap-2.5">
              <Tv className="w-6 h-6 text-orange-500" /> Voyo
            </h2>
            <div className="flex flex-wrap gap-2">
              <span className="badge flex items-center gap-1.5 bg-orange-500/10 border-orange-500/30 text-orange-400 font-black px-2.5 py-1 text-[10px] tracking-wider rounded-md">
                {variantLabel}
              </span>
              {voyoSvc?.authenticated && (
                <span className="badge flex items-center gap-1.5 bg-orange-500/10 border-orange-500/30 text-orange-400 font-black px-2.5 py-1 text-[10px] tracking-wider rounded-md">
                  <Lock className="w-3.5 h-3.5" /> AES-128 HLS
                </span>
              )}
            </div>
          </div>
          <p className="text-text-secondary text-sm">
            Preuzimanje filmova i serija sa Voyo.rs i Voyo.hr — AES-128 HLS, MKV izlaz.
          </p>
          <p className="text-xs text-text-muted mt-1.5">
            Primeri:{" "}
            <code className="font-mono text-orange-400 bg-white/[0.04] px-1.5 py-0.5 rounded">voyo.rs/film_50584.html</code>
            {" · "}
            <code className="font-mono text-orange-400 bg-white/[0.04] px-1.5 py-0.5 rounded">voyo.hr/...</code>
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
        <div className="md:col-span-2 glass-panel p-8 rounded-xl border border-glass flex flex-col gap-6 glow-orange-card glow-card-premium">
          <div>
            <label>Tip preuzimanja</label>
            <div className="sliding-tabs-wrapper">
              <div
                className="sliding-tabs-slider"
                style={{
                  width: "calc(50% - 4px)",
                  transform: `translateX(${voyoMode === "video" ? "0%" : "100%"})`,
                }}
              />
              <button
                type="button"
                onClick={() => {
                  setVoyoMode("video");
                  setVoyoSeriesData(null);
                }}
                className={`sliding-tabs-btn ${voyoMode === "video" ? "active" : ""}`}
              >
                <Film className="w-4 h-4" /> Film / epizoda
              </button>
              <button
                type="button"
                onClick={() => setVoyoMode("series")}
                className={`sliding-tabs-btn ${voyoMode === "series" ? "active" : ""}`}
              >
                <List className="w-4 h-4" /> Cela serija
              </button>
            </div>
          </div>

          <div>
            <label>{voyoMode === "video" ? "URL ili ID videa" : "URL ili ID serije / epizode"}</label>
            <div className="password-wrapper">
              {voyoMode === "video" ? (
                <Film className="absolute left-4 text-text-muted w-4 h-4" />
              ) : (
                <List className="absolute left-4 text-text-muted w-4 h-4" />
              )}
              <input
                type="text"
                placeholder={
                  voyoMode === "video"
                    ? "npr. https://voyo.rs/naslov_12345.html"
                    : "npr. https://voyo.hr/serije/540 ili link epizode"
                }
                value={voyoTarget}
                onChange={(e) => setVoyoTarget(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    if (voyoMode === "series") void searchVoyoSeries();
                    else void startVoyoDownload();
                  }
                }}
                className="input-premium pl-11 pr-24"
                style={cssVars({ "--focused-border": "#f97316", "--focused-glow": "rgba(249,115,22,0.25)" })}
              />
              {voyoMode === "series" && (
                <button
                  type="button"
                  onClick={() => void searchVoyoSeries()}
                  disabled={voyoSearching || !voyoTarget}
                  className="btn btn-premium-primary absolute right-1.5 top-1.5 bottom-1.5 h-auto py-1 px-4 text-xs font-bold"
                  style={cssVars({
                    "--btn-grad-start": "#f97316",
                    "--btn-grad-end": "#ea580c",
                    "--btn-glow": "rgba(249,115,22,0.25)",
                    "--btn-glow-hover": "rgba(249,115,22,0.45)",
                    height: "calc(100% - 6px)",
                    display: "flex",
                    alignItems: "center",
                  })}
                >
                  {voyoSearching ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Search className="w-3.5 h-3.5" />}
                  Pretraži
                </button>
              )}
            </div>
            {voyoMode === "video" && voyoPreviewLoading && (
              <p className="text-[10px] text-text-muted mt-1.5 flex items-center gap-1.5">
                <Loader2 className="w-3 h-3 animate-spin" /> Učitavam metapodatke...
              </p>
            )}
          </div>

          {voyoMode === "video" && voyoVideoPreview && (
            <div className="p-4 rounded-lg bg-orange-500/10 border border-orange-500/20 flex gap-3 items-start">
              {voyoVideoPreview.thumbnail && (
                <img
                  src={voyoVideoPreview.thumbnail}
                  alt=""
                  className="w-20 h-12 object-cover rounded border border-white/10"
                />
              )}
              <div className="flex-1 min-w-0">
                <p className="font-bold text-white text-sm truncate">{voyoVideoPreview.title}</p>
                {voyoVideoPreview.duration_str && (
                  <p className="text-xs text-text-muted mt-0.5">{voyoVideoPreview.duration_str}</p>
                )}
                {voyoVideoPreview && voyoIsHardBlocked(voyoVideoPreview) && (
                  <p className="text-[11px] font-bold text-red-400 mt-1">
                    {voyoVideoPreview.stream_reason || "Stream nije dostupan za preuzimanje."}
                  </p>
                )}
                {voyoVideoPreview && voyoIsSoftHint(voyoVideoPreview, ignoreCatalogDrmHint) && (
                  <p className="text-[11px] font-bold text-amber-400 mt-1">{VOYO_HINT_MSG}</p>
                )}
                {voyoVideoPreview?.probe_ok && voyoVideoPreview.streamable && voyoCatalogDrmHint(voyoVideoPreview) && (
                  <p className="text-[11px] font-bold text-emerald-400 mt-1">Stream je dostupan (AES-128 HLS).</p>
                )}
              </div>
            </div>
          )}

          {voyoMode === "series" && !voyoSeriesData && (
            <div>
              <label>Opseg epizoda (bez pretrage)</label>
              <div className="password-wrapper">
                <List className="absolute left-4 text-text-muted w-4 h-4" />
                <input
                  type="text"
                  placeholder="npr. 1-3,5 ili prazno za sve"
                  value={voyoEpisodesRange}
                  onChange={(e) => setVoyoEpisodesRange(e.target.value)}
                  className="input-premium pl-11"
                  style={cssVars({ "--focused-border": "#f97316", "--focused-glow": "rgba(249,115,22,0.25)" })}
                />
              </div>
              <p className="text-[10px] text-text-muted mt-1">Koristite „Pretraži” za listu epizoda po sezonama.</p>
            </div>
          )}

          <div>
            <label>Maks. rezolucija preuzimanja</label>
            <CustomSelect
              value={voyoRes}
              options={["2160p", "1080p", "720p", "480p"]}
              onChange={(val) => setVoyoRes(val)}
              formatLabel={(val) =>
                val === "2160p" ? "2160p (4K)" : val === "1080p" ? "1080p (Full HD)" : val === "720p" ? "720p (HD)" : "480p (SD)"
              }
            />
            <p className="text-[10px] text-text-muted mt-1">Bira najbolji HLS stream do izabrane visine.</p>
          </div>

          {voyoMode === "series" && voyoSeriesData && (
            <VoyoSeasonList
              voyoSeriesData={voyoSeriesData}
              selectedVoyoEpisodes={selectedVoyoEpisodes}
              setSelectedVoyoEpisodes={setSelectedVoyoEpisodes}
              ignoreCatalogDrmHint={ignoreCatalogDrmHint}
            />
          )}

          <button
            type="button"
            onClick={() => void startVoyoDownload()}
            disabled={ctaDisabled}
            className="btn-premium btn-premium-primary w-full py-4 text-base font-extrabold"
            style={cssVars({
              "--btn-grad-start": "#f97316",
              "--btn-grad-end": "#ea580c",
              "--btn-glow": "rgba(249,115,22,0.3)",
              "--btn-glow-hover": "rgba(249,115,22,0.45)",
            })}
          >
            {voyoSubmitting ? (
              <>
                <Loader2 className="w-5 h-5 animate-spin" /> Slanje...
              </>
            ) : (
              <>
                <Download className="w-5 h-5" /> {ctaLabel}
              </>
            )}
          </button>
        </div>

        <div className="flex flex-col gap-6">
          <div className="glass-panel p-6 rounded-xl border border-glass glow-orange-card glow-card-premium">
            <h3 className="font-extrabold text-base mb-4 flex items-center gap-2 text-white">
              <User className="w-5 h-5 text-orange-400" />
              Status naloga
            </h3>

            {voyoSvc?.authenticated ? (
              <div className="flex flex-col gap-3">
                <span
                  className="badge flex items-center gap-1.5 bg-emerald-500/10 border-emerald-500/30 text-emerald-400 font-black px-2.5 py-1 text-[10px] tracking-wider rounded-md w-max"
                  style={cssVars({ animation: "pulseGlowBrighter 2s infinite", "--glow-color": "rgba(16, 185, 129, 0.2)" })}
                >
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 shadow-[0_0_8px_#34d399]" />
                  Prijavljen
                </span>
                {voyoSvc.nickname && (
                  <p className="text-xs text-text-secondary">
                    Profil: <span className="text-white font-semibold">{voyoSvc.nickname}</span>
                  </p>
                )}
                <div className="flex flex-col gap-1.5 border-t border-white/[0.03] pt-3">
                  <p className="text-xs font-bold text-text-secondary">E-mail:</p>
                  <p className="text-sm font-semibold text-white truncate bg-black/20 p-2 rounded border border-white/[0.02]">
                    {voyoSvc.email}
                  </p>
                </div>
                <div className="flex justify-between items-center text-xs font-semibold text-white bg-black/10 p-2 rounded">
                  <span className="text-text-secondary">Pretplata:</span>
                  <span className={voyoSvc.subscribed ? "text-emerald-400 font-black" : "text-red-400 font-black"}>
                    {voyoSvc.subscribed ? "Aktivna" : "Neaktivna"}
                  </span>
                </div>
              </div>
            ) : (
              <div className="flex flex-col gap-3">
                <span className="badge flex items-center gap-1.5 bg-red-500/10 border-red-500/30 text-red-400 font-black px-2.5 py-1 text-[10px] tracking-wider rounded-md w-max">
                  Nije prijavljen
                </span>
                <p className="text-xs text-text-secondary leading-relaxed">
                  Prijavite se u Postavkama sa Voyo nalogom za izabrani region.
                </p>
                <button
                  type="button"
                  onClick={() => setActiveTab("settings")}
                  className="text-xs font-bold text-orange-400 flex items-center gap-1.5 hover:underline w-max"
                >
                  <Settings className="w-3.5 h-3.5" /> Otvori Postavke
                  <ExternalLink className="w-3 h-3 opacity-60" />
                </button>
              </div>
            )}
          </div>

          <div className="glass-panel p-6 rounded-xl border border-glass flex flex-col gap-4 glow-orange-card glow-card-premium">
            <h4 className="font-extrabold text-sm flex items-center gap-2 text-orange-400 border-b border-white/[0.04] pb-3">
              <ShieldAlert className="w-4 h-4" />
              HLS engine (RS / HR)
            </h4>
            <p className="text-xs text-text-secondary leading-relaxed">
              Voyo koristi AES-128 HLS (bez Widevine CDM). Preuzimač paralelno skida segmente, dekriptuje i remux-uje u MKV.
            </p>
            <ul className="text-xs text-text-secondary flex flex-col gap-2 border-t border-white/[0.03] pt-3">
              <li>• Paralelno HLS preuzimanje + yt-dlp rezerva</li>
              <li>• Automatsko SxxExx imenovanje fajlova</li>
              <li>• Widevine DRM naslovi nisu podržani</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
}
