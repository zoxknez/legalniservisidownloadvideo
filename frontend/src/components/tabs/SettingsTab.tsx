import { useState } from "react";
import {
  AlertCircle,
  Check,
  CheckCircle2,
  Clapperboard,
  Copy,
  Database,
  Download,
  Film,
  FolderOpen,
  Info,
  Loader2,
  Play,
  Radio,
  Server,
  Settings,
  ShieldAlert,
  Sparkles,
  Tv,
  Zap,
} from "lucide-react";
import { CustomSelect } from "../CustomSelect";
import { BinaryPathCard } from "../BinaryPathCard";
import {
  CredentialsSecurityPanel,
  WvdInstallerPanel,
  SessionConsoleScriptHint,
} from "../SecurityPanels";
import {
  ALL_SESSIONS_BOOKMARKLET,
  ALL_SESSIONS_CLIPBOARD_BOOKMARKLET,
  HBO_SNIFFER_BOOKMARKLET,
} from "../../lib/sessionConsoleScripts";
import { USERSCRIPT_INSTALL_URL, fetchUserscriptText } from "../../lib/bridge";
import { SESSION_IMPORT_PLACEHOLDERS } from "../../lib/sessionConsoleScripts";
import { apiFetch, setStoredApiKey } from "../../lib/api";
import type { BinaryStatus, TranscodeAcceleration } from "../../types/app";
import { useSettingsTab } from "../../hooks/domains/useSettingsTab";
import { SettingsDrmCard } from "../settings/SettingsDrmCard";
import { SettingsServiceGrid } from "../settings/SettingsServiceGrid";
import { SettingsCredentialFooter } from "../settings/SettingsCredentialFooter";
import { cssVars } from "../../utils/cssVars";

const SETTINGS_SECTIONS = [
  { id: "settings-auth", label: "Autentifikacija" },
  { id: "settings-security", label: "Sigurnost" },
  { id: "settings-wvd", label: "WVD / CDM" },
  { id: "settings-services", label: "Servisi" },
  { id: "settings-system", label: "Sistem" },
  { id: "settings-session", label: "Uvoz sesije" },
  { id: "settings-sniffer", label: "Sniffer" },
  { id: "settings-credentials", label: "Kredencijali" },
] as const;

function formatStorageBytes(bytes?: number): string {
  if (!bytes || bytes <= 0) return "0 B";
  const units = ["B", "KB", "MB", "GB", "TB"];
  const exponent = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
  const value = bytes / 1024 ** exponent;
  return `${value.toFixed(value >= 10 || exponent === 0 ? 0 : 1)} ${units[exponent]}`;
}

export function SettingsTab() {
  const {
    apiKeyInput,
    autoSyncLoading,
    binariesPaths,
    deviceWvdInfo,
    eonNumber,
    eonPassword,
    eonSerial,
    eonStatus,
    eonUsername,
    fetchStatus,
    fetchTranscodeDiagnostics,
    handleAutoSyncBrowser,
    handleClearCredentials,
    clearingService,
    handleImportSession,
    handleSaveApiKeyToServer,
    savingApiKey,
    handleMigrateCredentials,
    migratingCredentials,
    handleSaveConfig,
    savingConfig,
    submittingLogin,
    hrtiEmail,
    hrtiPassword,
    importLoading,
    importService,
    importSessionData,
    openOutputFolder,
    outputDir,
    selectOutputFolder,
    selectingOutputDir,
    rtsEmail,
    rtsPassword,
    saveFeedback,
    saveSnifferAutoDownload,
    setApiKeyInput,
    setBinariesPaths,
    setEonNumber,
    setEonPassword,
    setEonSerial,
    setEonUsername,
    setHrtiEmail,
    setHrtiPassword,
    setImportService,
    setImportSessionData,
    setOutputDir,
    setRtsEmail,
    setRtsPassword,
    setShowEonPass,
    setShowHrtiPass,
    setShowRtsPass,
    setShowVoyoPass,
    setSnifferScriptCopied,
    setTranscodeMode,
    setVoyoEmail,
    setVoyoPassword,
    showEonPass,
    showHrtiPass,
    showRtsPass,
    showToast,
    setActiveTab,
    browserSyncSupported,
    showVoyoPass,
    snifferAutoDownload,
    snifferScriptCopied,
    status,
    submitLogin,
    transcodeDiagnostics,
    transcodeMode,
    userscriptPreview,
    voyoEmail,
    voyoPassword,
    voyoVariant,
    setVoyoVariant,
    voyoProfiles,
    voyoActiveProfileId,
    voyoProfileSwitching,
    selectVoyoProfile,
    hboMarket,
    setHboMarket,
    startHboLogin,
    hboSubmitting,
    hboAuth,
    skyshowtimeAuth,
    startSkyshowtimeBrowserSync,
    skyshowtimeSubmitting,
    ytdlpUpdating,
    handleUpdateYtdlp,
    ytdlpNameTemplate,
    setYtdlpNameTemplate,
    maxConcurrentDownloads,
    setMaxConcurrentDownloads,
    voyoIgnoreCatalogDrmHint,
    setVoyoIgnoreCatalogDrmHint,
    outputFormat,
    setOutputFormat,
  } = useSettingsTab();

  const [notificationsEnabled, setNotificationsEnabled] = useState(
    () => localStorage.getItem("notifications_enabled") === "true"
  );
  const [notificationPermission, setNotificationPermission] = useState(
    () => typeof window !== "undefined" && "Notification" in window ? Notification.permission : "default"
  );

  const outputDisk = status?.system_metrics?.disk;

  const handleToggleNotifications = async () => {
    if (!("Notification" in window)) {
      showToast("Vaš pretraživač ne podržava desktop obaveštenja.", "error");
      return;
    }

    if (notificationsEnabled) {
      localStorage.setItem("notifications_enabled", "false");
      setNotificationsEnabled(false);
      showToast("Desktop obaveštenja onemogućena.", "info");
    } else {
      let permission = Notification.permission;
      if (permission === "default") {
        permission = await Notification.requestPermission();
        setNotificationPermission(permission);
      }

      if (permission === "granted") {
        localStorage.setItem("notifications_enabled", "true");
        setNotificationsEnabled(true);
        showToast("Desktop obaveštenja uspešno omogućena!", "success");
        new Notification("Obaveštenja aktivirana", {
          body: "Sada ćete dobijati obaveštenja o završenim preuzetim fajlovima i transkodovanju.",
        });
      } else {
        localStorage.setItem("notifications_enabled", "false");
        setNotificationsEnabled(false);
        showToast("Dozvola za obaveštenja je odbijena u brauzeru.", "error");
      }
    }
  };
  return (
<div key="settings" className="tab-content tab-content-settings">
    <div className="tab-page-header tab-header-settings mb-8">
      <div className="tab-page-header-icon animate-pulse" style={{background:"linear-gradient(135deg,#6366f1,#4f46e5)"}}>
        <Settings style={{width:24,height:24,color:"white"}} />
      </div>
      <div style={{flex:1}}>
        <h2 className="text-2xl font-extrabold text-white mb-1 flex items-center gap-2.5">
          <Settings className="w-6 h-6 text-indigo-400" /> Postavke Aplikacije
        </h2>
        <p className="text-text-secondary text-sm">Podesite kredencijale za servise, izlazni direktorijum i putanje do eksternih alata.</p>
      </div>
    </div>

    <nav className="flex flex-wrap gap-2 mb-2 pb-4 border-b border-white/[0.04]">
      {SETTINGS_SECTIONS.map(({ id, label }) => (
        <a
          key={id}
          href={`#${id}`}
          className="text-[10px] font-bold uppercase tracking-wider px-2.5 py-1 rounded-md border border-white/10 text-text-muted hover:text-white hover:border-indigo-500/40 transition-colors"
        >
          {label}
        </a>
      ))}
    </nav>

    <div className="flex flex-col gap-8">

      {/* Zero-Friction Authentication Panel */}
      <div id="settings-auth" className="glass-panel p-8 rounded-xl border border-glass glow-indigo-card glow-card-premium relative overflow-hidden scroll-mt-24">
        <div className="console-scanline" />
        <div className="flex items-center justify-between gap-4 flex-wrap mb-6 pb-4 border-b border-white/[0.04]">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-purple-600 to-indigo-600 flex items-center justify-center shadow-lg">
              <Sparkles className="w-5 h-5 text-white animate-pulse" />
            </div>
            <div>
              <h3 className="font-extrabold text-base text-white tracking-wide uppercase">Zero-Friction Autentifikacija</h3>
              <p className="text-text-secondary text-xs">Uvezite sesije jednim klikom direktno iz vašeg pretraživača</p>
            </div>
          </div>
          {!browserSyncSupported && (
            <p className="text-[11px] text-amber-300 bg-amber-500/10 border border-amber-500/25 rounded-lg px-3 py-2 m-0 w-full">
              Automatska sinhronizacija iz Chrome/Edge/Brave radi samo na <strong>Windows</strong>-u.
              Na ovom sistemu koristite bookmarklet ili ručni uvoz sesije.
            </p>
          )}
          <button
            type="button"
            onClick={handleAutoSyncBrowser}
            disabled={autoSyncLoading || !browserSyncSupported}
            title={!browserSyncSupported ? "Dostupno samo na Windows-u" : undefined}
            className="py-2.5 px-5 rounded-lg text-xs font-black tracking-wider uppercase bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 text-white flex items-center gap-2 transition-all duration-300 shadow-[0_0_15px_rgba(99,102,241,0.4)] disabled:opacity-50"
          >
            {autoSyncLoading ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Sparkles className="w-4 h-4 text-amber-300" />
            )}
            {autoSyncLoading ? "Sinhronizuje se..." : "Sinhronizuj iz pretraživača"}
          </button>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Left: Info */}
          <div className="flex flex-col gap-3">
            <h4 className="font-bold text-xs text-indigo-300 tracking-wider uppercase">Kako funkcioniše automatski uvoz?</h4>
            <p className="text-xs text-text-secondary leading-relaxed">
              Aplikacija bezbedno skenira lokalne profile instaliranih pretraživača (**Chrome, Edge, Brave**) na vašem računaru i dešifruje aktivne sesijske kolačiće za <strong className="text-white">RTS Planetu, EON TV, Voyo, HRTi i SkyShowtime</strong> koristeći Windows DPAPI zaštitu. Za <strong className="text-white">HBO Max</strong> koristite uvoz sesije ili bookmarklet ispod.
            </p>
            <div className="p-3.5 rounded-lg bg-black/40 border border-white/[0.04] text-[11px] text-text-muted flex flex-col gap-2">
              <span className="flex items-center gap-1.5 text-amber-400 font-bold">
                <Info className="w-3.5 h-3.5" /> Savet za uspešnu sinhronizaciju:
              </span>
              <span>1. Proverite da li ste prijavljeni na ciljne servise u vašem uobičajenom pretraživaču.</span>
              <span>2. Ukoliko dobijete grešku o zaključanoj bazi, nakratko zatvorite pretraživač i probajte ponovo.</span>
            </div>
          </div>

          {/* Right: Bookmarklets */}
          <div className="flex flex-col gap-3">
            <h4 className="font-bold text-xs text-purple-300 tracking-wider uppercase">1-Klik Bookmarkleti (direktno u app)</h4>
            <p className="text-xs text-text-secondary leading-relaxed">
              Prevucite link u Bookmark bar. Klik na sajtu servisa (Voyo, HRTi, RTS, Max, EON) šalje sesiju na{" "}
              <code className="font-mono bg-white/10 px-1 rounded">127.0.0.1:8200</code> — bez copy-paste.
              Aplikacija mora biti pokrenuta (<code className="font-mono">python run.py</code>).
            </p>
            
            <div className="flex flex-col gap-2.5">
              <a
                href={ALL_SESSIONS_BOOKMARKLET}
                onClick={(e) => {
                  e.preventDefault();
                  navigator.clipboard.writeText(ALL_SESSIONS_BOOKMARKLET);
                  showToast("Bookmarklet kopiran — dodajte kao bookmark URL ili prevucite na traku.", "success");
                }}
                className="bookmarklet-btn block p-3 text-center rounded-lg text-xs font-bold text-white border border-dashed border-indigo-500/30 hover:border-indigo-400 hover:bg-indigo-500/10 transition-all cursor-grab active:cursor-grabbing"
                title="Kliknite da kopirate kod ili prevucite na Bookmark bar"
              >
                🖱️ ⚡ Pošalji sesiju u app (automatski)
              </a>
              <button
                type="button"
                onClick={() => {
                  navigator.clipboard.writeText(ALL_SESSIONS_CLIPBOARD_BOOKMARKLET.replace(/^javascript:/, "javascript:"));
                  showToast("Fallback bookmarklet (clipboard JSON) kopiran.", "info");
                }}
                className="text-[10px] text-text-muted underline self-start"
              >
                Alternativa: samo kopiraj JSON u clipboard
              </button>
              
              <a
                href={HBO_SNIFFER_BOOKMARKLET}
                onClick={() => {
                  navigator.clipboard.writeText(HBO_SNIFFER_BOOKMARKLET);
                  showToast("Sniffer Bookmarklet kopiran! Možete ga zalepiti kao adresu novog bookmark-a.", "success");
                }}
                className="bookmarklet-btn block p-3 text-center rounded-lg text-xs font-bold text-white border border-dashed border-purple-500/30 hover:border-purple-400 hover:bg-purple-500/10 transition-all cursor-grab active:cursor-grabbing"
                title="Kliknite da kopirate kod ili prevucite na Bookmark bar"
              >
                🖱️ Prevucite / Kopirajte: 🎥 Max/HBO Snifer
              </a>
            </div>
          </div>
        </div>
      </div>

      <div id="settings-security" className="scroll-mt-24">
        <CredentialsSecurityPanel
          credentialsSecurity={status?.credentials_security}
          onMigrate={() => void handleMigrateCredentials()}
          migrating={migratingCredentials}
        />
      </div>

      <div id="settings-wvd" className="scroll-mt-24 flex flex-col gap-5">
      <WvdInstallerPanel
        deviceFound={deviceWvdInfo?.found}
        onInstalled={() => {
          fetchStatus();
          fetchTranscodeDiagnostics();
          void apiFetch("/api/drm/reload", { method: "POST" });
        }}
        showToast={showToast}
      />
      {status && <SettingsDrmCard drm={status.drm} onOpenDrmTab={() => setActiveTab("drm")} />}
      </div>

      {/* F3: Services Authentication Status Overview */}
      {status && (
        <div id="settings-services" className="glass-panel p-6 rounded-xl border border-glass glow-indigo-card glow-card-premium scroll-mt-24">
          <h3 className="font-extrabold text-base mb-4 flex items-center gap-2 text-white">
            <Server className="w-4 h-4 text-indigo-400" />
            Pregled Autentifikacije Servisa
          </h3>
          <SettingsServiceGrid status={status} />
        </div>
      )}

      {/* Folder and Binaries Status */}
      <div id="settings-system" className="glass-panel p-8 rounded-xl border border-glass flex flex-col gap-6 glow-indigo-card glow-card-premium scroll-mt-24">
        <h3 className="font-extrabold text-xl text-indigo-400 flex items-center gap-2">
          <Settings className="w-5 h-5" />
          Sistemska Podešavanja
        </h3>

        <div>
          <label>Izlazni folder za preuzete filmove/serije (Output Directory)</label>
          <div className="flex flex-col md:flex-row gap-2">
            <input
              type="text"
              value={outputDir}
              onChange={(e) => setOutputDir(e.target.value)}
              className="input-premium font-mono text-xs truncate flex-1"
              style={cssVars({"--focused-border": "#6366f1", "--focused-glow": "rgba(99,102,241,0.25)"})}
            />
            <button
              type="button"
              onClick={() => void selectOutputFolder()}
              disabled={selectingOutputDir || savingConfig}
              className="py-2.5 px-4 rounded-lg text-xs font-black tracking-wider uppercase bg-indigo-600 hover:bg-indigo-500 text-white flex items-center justify-center gap-2 transition-all disabled:opacity-50"
            >
              {selectingOutputDir ? <Loader2 className="w-4 h-4 animate-spin" /> : <FolderOpen className="w-4 h-4" />}
              {selectingOutputDir ? "Biranje..." : "Izaberi folder"}
            </button>
          </div>
          <div className="flex flex-wrap gap-2 mt-2">
            <button
              type="button"
              onClick={() => void handleSaveConfig()}
              disabled={savingConfig || !outputDir.trim()}
              className="text-xs font-bold text-emerald-400 hover:text-emerald-300 px-2 py-1 rounded border border-emerald-500/20 disabled:opacity-50"
            >
              Sačuvaj unetu putanju
            </button>
            <button
              type="button"
              onClick={openOutputFolder}
              className="text-xs font-bold text-indigo-400 hover:text-indigo-300 px-2 py-1 rounded border border-indigo-500/20"
            >
              Otvori folder
            </button>
          </div>
          <p className="text-[10px] text-text-muted mt-1.5">
            * Svi preuzeti video fajlovi biće sačuvani na ovoj lokaciji.
            {outputDisk && (
              <span className="block mt-1 text-indigo-300/90">
                Slobodno na izabranom disku: {formatStorageBytes(outputDisk.free)} od {formatStorageBytes(outputDisk.total)} ({outputDisk.percent}% zauzeto).
              </span>
            )}
            <span className="block mt-1 text-amber-300/90">
              Na RDP/LAN instalaciji folder se bira na računaru gde je aplikacija pokrenuta.
            </span>
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mt-2 border-t border-white/[0.04] pt-4">
          <div>
            <label className="block text-xs font-bold text-indigo-300 tracking-wider uppercase mb-2">Šablon Imena Fajla (yt-dlp)</label>
            <input
              type="text"
              value={ytdlpNameTemplate}
              onChange={(e) => setYtdlpNameTemplate(e.target.value)}
              placeholder="%(title)s.%(ext)s"
              maxLength={240}
              className="input-premium font-mono text-xs w-full"
              style={cssVars({"--focused-border": "#6366f1", "--focused-glow": "rgba(99,102,241,0.25)"})}
            />
            <p className="text-[10px] text-text-muted mt-1.5 leading-relaxed">
              * Određuje format imena fajla za yt-dlp. Podržani placeholderi: 
              <br />
              <code className="font-mono bg-white/5 px-1 rounded">%(title)s</code>, <code className="font-mono bg-white/5 px-1 rounded">%(id)s</code>, <code className="font-mono bg-white/5 px-1 rounded">%(ext)s</code>
            </p>
          </div>

          <div>
            <label className="block text-xs font-bold text-indigo-300 tracking-wider uppercase mb-2">Maksimalan Broj Istovremenih Preuzimanja</label>
            <select
              value={maxConcurrentDownloads}
              onChange={(e) => setMaxConcurrentDownloads(parseInt(e.target.value, 10))}
              className="input-premium font-semibold text-xs py-2 px-3 rounded-lg bg-black/45 text-white border border-white/10 outline-none w-full focus:border-indigo-500 focus:shadow-[0_0_10px_rgba(99,102,241,0.25)] transition-all"
            >
              {[1, 2, 3, 4, 5].map((num) => (
                <option key={num} value={num}>
                  {num} {num === 1 ? "aktivno preuzimanje" : num < 5 ? "aktivna preuzimanja" : "aktivnih preuzimanja"}
                </option>
              ))}
            </select>
            <p className="text-[10px] text-text-muted mt-1.5">
              * Globalni limit aktivnih preuzimanja u redu. Ostala preuzimanja će čekati slobodan slot.
            </p>
          </div>

          <div>
            <label className="block text-xs font-bold text-indigo-300 tracking-wider uppercase mb-2">Format spremanja videa</label>
            <select
              value={outputFormat}
              onChange={(e) => setOutputFormat(e.target.value)}
              className="input-premium font-semibold text-xs py-2 px-3 rounded-lg bg-black/45 text-white border border-white/10 outline-none w-full focus:border-indigo-500 focus:shadow-[0_0_10px_rgba(99,102,241,0.25)] transition-all"
            >
              <option value="mp4">MP4 (.mp4)</option>
              <option value="mkv">MKV (.mkv)</option>
            </select>
            <p className="text-[10px] text-text-muted mt-1.5">
              * Podrazumevani video kontejner format. MKV podržava više audio zapisa i titlova, dok je MP4 kompatibilniji sa starijim uređajima.
            </p>
          </div>
        </div>

        <div className="border-t border-white/[0.04] pt-4">
          <label className="block text-xs font-bold text-indigo-300 tracking-wider uppercase mb-2">Desktop i Browser Notifikacije</label>
          <div className="flex items-center gap-4 flex-wrap">
            <button
              type="button"
              onClick={handleToggleNotifications}
              className={`py-2 px-4 rounded-lg text-xs font-bold border transition-all flex items-center gap-2 ${
                notificationsEnabled && notificationPermission === "granted"
                  ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/30"
                  : "bg-white/5 text-text-secondary border-white/10 hover:bg-white/10"
              }`}
            >
              <span className={`w-2 h-2 rounded-full ${notificationsEnabled && notificationPermission === "granted" ? "bg-emerald-400 animate-pulse" : "bg-text-muted"}`} />
              {notificationsEnabled && notificationPermission === "granted" ? "Notifikacije: Omogućene" : "Omogući desktop notifikacije"}
            </button>
            <span className="text-[10px] text-text-muted">
              Status dozvole u brauzeru: <strong className="text-white">{notificationPermission.toUpperCase()}</strong>
            </span>
          </div>
          <p className="text-[10px] text-text-muted mt-1.5">
            * Slanje sistemskih obaveštenja kada se preuzimanje ili hardverska kompresija završi ili ne uspe.
          </p>
        </div>

        <div>
          <label>API ključ (LAN / udaljeni pristup)</label>
          <input
            type="password"
            value={apiKeyInput}
            onChange={(e) => setApiKeyInput(e.target.value)}
            placeholder="Iz ~/.videodownload/config.json (server.api_key)"
            className="input-premium font-mono text-xs"
            style={cssVars({"--focused-border": "#6366f1", "--focused-glow": "rgba(99,102,241,0.25)"})}
          />
          <div className="flex flex-wrap gap-2 mt-2">
            <button
              type="button"
              className="text-xs font-bold text-indigo-400 hover:text-indigo-300 px-2 py-1 rounded border border-indigo-500/20"
              onClick={() => {
                setStoredApiKey(apiKeyInput);
                showToast("API ključ sačuvan u pregledaču (localStorage).", "success");
              }}
            >
              Sačuvaj lokalno
            </button>
            <button
              type="button"
              disabled={savingApiKey || !apiKeyInput.trim()}
              className="text-xs font-bold text-emerald-400 hover:text-emerald-300 px-2 py-1 rounded border border-emerald-500/20 disabled:opacity-50"
              onClick={() => void handleSaveApiKeyToServer()}
            >
              {savingApiKey ? (
                <span className="flex items-center gap-1.5">
                  <Loader2 className="w-3 h-3 animate-spin" />
                  Čuvanje…
                </span>
              ) : (
                "Sačuvaj na server"
              )}
            </button>
          </div>
          <p className="text-[10px] text-text-muted mt-1.5">
            Lokalno = header u frontendu; na server = <code className="font-mono bg-white/[0.04] px-1 rounded">~/.videodownload/config.json</code>.
            Na localhost-u ključ obično nije potreban. Potreban je za LAN pristup.
            {status?.server?.api_key_configured ? (
              <span className="block mt-1 text-emerald-400/90">Server ima podešen API ključ.</span>
            ) : (
              <span className="block mt-1 text-amber-400/90">
                Server još nema API ključ u config.json — prvi start ga može generisati automatski.
              </span>
            )}
          </p>
          <div className="mt-2 grid grid-cols-1 md:grid-cols-2 gap-2 text-[10px]">
            <div className="p-2 rounded-lg bg-white/[0.03] border border-white/[0.05]">
              <span className="text-text-muted">Javni URL za bridge:</span>{" "}
              <span className="font-mono text-indigo-200 break-all">
                {status?.network?.public_backend_url || "nije podešen"}
              </span>
            </div>
            <div className="p-2 rounded-lg bg-white/[0.03] border border-white/[0.05]">
              <span className="text-text-muted">Regionalni proxy:</span>{" "}
              <span className={status?.network?.outbound_proxy_configured ? "font-mono text-emerald-300 break-all" : "text-amber-300"}>
                {status?.network?.outbound_proxy_configured
                  ? status?.network?.outbound_proxy || "aktivan"
                  : "nije podešen"}
              </span>
            </div>
          </div>
        </div>

        <div className="mt-2 border-t border-white/[0.04] pt-4">
          <label className="block text-xs font-bold text-indigo-300 tracking-wider uppercase mb-2">GPU Hardverska Kompresija (Nakon preuzimanja)</label>
          <div className="flex items-center gap-3">
            <select
              value={transcodeMode}
              onChange={(e) => setTranscodeMode(e.target.value)}
              className="input-premium font-semibold text-xs py-2 px-3 rounded-lg bg-black/45 text-white border border-white/10 outline-none focus:border-indigo-500 focus:shadow-[0_0_10px_rgba(99,102,241,0.25)] transition-all flex-1"
            >
              <option value="off">Isključeno (Bez automatske kompresije)</option>
              <option value="hevc">HEVC / H.265 (Hardware Accelerated - Preporučeno)</option>
              <option value="av1">AV1 (Hardware Accelerated - Maksimalna ušteda prostora)</option>
            </select>
          </div>
          <p className="text-[10px] text-text-muted mt-2">
            * FFmpeg će automatski detektovati vaš GPU (NVIDIA NVENC, Intel QSV, AMD AMF, Apple Silicon) i komprimovati gotove video fajlove uz **30-50% uštede diska** bez vidljivog gubitka kvaliteta slike.
          </p>

          {/* High-Tech GPU Diagnostics & Capabilities Dashboard Card */}
          {transcodeDiagnostics && (
            <div className="mt-4 p-4 rounded-xl bg-gradient-to-br from-indigo-950/20 to-purple-950/20 border border-indigo-500/10 glow-indigo-card flex flex-col gap-4 relative overflow-hidden animate-pulse-subtle">
              <div className="flex items-center justify-between flex-wrap gap-2 pb-2.5 border-b border-white/[0.04]">
                <div className="flex items-center gap-2">
                  <Database className="w-4.5 h-4.5 text-indigo-400 animate-pulse" />
                  <div>
                    <span className="text-[9px] text-text-muted font-black tracking-wider uppercase block">Detektovani Video Procesor (GPU)</span>
                    <span className="font-extrabold text-xs text-white block">{transcodeDiagnostics.gpu_name}</span>
                  </div>
                </div>
                <span className="badge bg-emerald-500/10 border-emerald-500/20 text-emerald-400 font-black px-2 py-0.5 text-[9px] tracking-wider rounded">
                  GPU AKTIVAN
                </span>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
                <div className="flex flex-col gap-1.5 p-3 rounded-lg bg-black/30 border border-white/[0.02]">
                  <span className="text-[9px] text-text-muted font-bold tracking-wider uppercase">HEVC (H.265) Hardware Kodiranje</span>
                  {transcodeDiagnostics.available_codecs?.hevc?.supported ? (
                    <div className="flex flex-col gap-0.5">
                      <span className="text-xs font-black text-emerald-400 flex items-center gap-1">
                        <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 flex-shrink-0" />
                        Podržano (Hardverski)
                      </span>
                      <span className="text-[9px] text-text-muted font-mono">
                        Encoder: {transcodeDiagnostics.available_codecs?.hevc?.encoder_used}
                      </span>
                    </div>
                  ) : (
                    <span className="text-xs font-black text-text-muted flex items-center gap-1">
                      <AlertCircle className="w-3.5 h-3.5 text-text-muted flex-shrink-0" />
                      Nije podržano
                    </span>
                  )}
                </div>

                <div className="flex flex-col gap-1.5 p-3 rounded-lg bg-black/30 border border-white/[0.02]">
                  <span className="text-[9px] text-text-muted font-bold tracking-wider uppercase">AV1 Hardware Kodiranje</span>
                  {transcodeDiagnostics.available_codecs?.av1?.supported ? (
                    <div className="flex flex-col gap-0.5">
                      <span className="text-xs font-black text-indigo-400 flex items-center gap-1">
                        <CheckCircle2 className="w-3.5 h-3.5 text-indigo-400 flex-shrink-0" />
                        Podržano (Hardverski)
                      </span>
                      <span className="text-[9px] text-text-muted font-mono">
                        Encoder: {transcodeDiagnostics.available_codecs?.av1?.encoder_used}
                      </span>
                    </div>
                  ) : (
                    <span className="text-xs font-black text-text-muted flex items-center gap-1">
                      <AlertCircle className="w-3.5 h-3.5 text-text-muted flex-shrink-0" />
                      Nije podržano
                    </span>
                  )}
                </div>
              </div>

              <div className="flex flex-col gap-1.5 mt-1">
                <span className="text-[9px] text-text-muted font-bold tracking-wider uppercase">Aktivna Ubrzanja na Sistemu:</span>
                <div className="flex flex-wrap gap-1.5">
                  {transcodeDiagnostics.accelerations && Object.entries(transcodeDiagnostics.accelerations).map(([key, rawAccel]) => {
                    const accel = rawAccel as TranscodeAcceleration;
                    return (
                    <span key={key} 
                      className={`px-2 py-1 rounded text-[9px] font-extrabold border transition-all ${
                        accel.supported
                          ? "bg-indigo-500/10 text-indigo-400 border-indigo-500/30"
                          : "bg-white/[0.01] text-text-muted border-white/[0.03] line-through decoration-white/20"
                      }`}
                      title={accel.description}
                    >
                      {accel.label}
                    </span>
                  );})}
                </div>
              </div>
            </div>
          )}
        </div>

        <div className="border-t border-white/[0.04] pt-6">
          <h4 className="font-bold text-sm text-white mb-4">Detektovani Eksterni Alati & CDM</h4>
          
          <div className="exec-monitor-grid">
            {status && Object.entries(status.binaries).map(([name, rawInfo]) => {
              const info = rawInfo as BinaryStatus;
              return (
              <BinaryPathCard
                key={name}
                name={name}
                found={info.found}
                pathValue={binariesPaths[name] || ""}
                onChange={(val) => setBinariesPaths({ ...binariesPaths, [name]: val })}
                showToast={showToast}
              />
            );})}
          </div>

          <div className="mt-4 flex flex-col gap-2.5 bg-black/20 p-4 rounded-xl border border-white/[0.04] max-w-md">
            <h5 className="font-bold text-xs text-indigo-300 uppercase tracking-wider">Ažuriranje zavisnosti alata</h5>
            <div className="flex items-center justify-between gap-4">
              <div className="flex flex-col gap-0.5">
                <span className="text-xs font-bold text-white">yt-dlp biblioteka</span>
                <span className="text-[10px] text-text-secondary">Preuzmite najnovije popravke direktno sa pip-a.</span>
              </div>
              <button
                type="button"
                onClick={handleUpdateYtdlp}
                disabled={ytdlpUpdating}
                className="py-1.5 px-4 rounded-lg text-[10px] font-black tracking-wider uppercase bg-indigo-600 hover:bg-indigo-500 text-white flex items-center gap-1.5 transition-all disabled:opacity-50"
              >
                {ytdlpUpdating ? (
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                ) : (
                  <Sparkles className="w-3.5 h-3.5 text-amber-300" />
                )}
                {ytdlpUpdating ? "Ažuriranje..." : "Ažuriraj yt-dlp"}
              </button>
            </div>
          </div>
        </div>

        <button
          onClick={handleSaveConfig}
          disabled={saveFeedback || savingConfig}
          className={`btn-premium self-end transition-all ${saveFeedback ? "bg-emerald-600 text-white border border-emerald-500 shadow-emerald" : "btn-premium-primary"}`}
          style={cssVars({
            "--btn-grad-start": "#6366f1",
            "--btn-grad-end": "#4f46e5",
            "--btn-glow": "rgba(99,102,241,0.25)",
            "--btn-glow-hover": "rgba(99,102,241,0.45)"
          })}
        >
          {saveFeedback ? (
            <span className="flex items-center gap-2">
              <Check className="w-4 h-4 animate-bounce" />
              Podešavanja sačuvana!
            </span>
          ) : savingConfig ? (
            <span className="flex items-center gap-2">
              <Loader2 className="w-4 h-4 animate-spin" />
              Čuvanje…
            </span>
          ) : (
            "Sačuvaj Podešavanja"
          )}
        </button>
      </div>

      {/* Session / Cookie Import Panel to bypass CAPTCHA */}
      <div id="settings-session" className="glass-panel p-8 rounded-xl border border-glass flex flex-col gap-6 glow-amber-card glow-card-premium scroll-mt-24">
        <h3 className="font-extrabold text-xl text-amber-400 flex items-center gap-2">
          <ShieldAlert className="w-5 h-5 text-amber-400 animate-pulse" />
          Uvoz Sesije / Kolačića (Bypass CAPTCHA)
        </h3>
        <p className="text-sm text-text-secondary leading-relaxed m-0">
          Ukoliko neki od servisa (RTS, Voyo, HRTi, HBO, EON) zahteva CAPTCHA zaštitu ili verifikaciju na formi za logovanje,
          možete se ulogovati normalno u vašem brauzeru, kopirati token ili sesiju (npr. preko EditThisCookie ekstenzije) i uvesti ga ovde.
        </p>
        <div className="p-3.5 rounded-lg bg-amber-500/10 border border-amber-500/25 text-[11px] text-amber-100 leading-relaxed">
          <span className="font-extrabold text-amber-300">RDP / udaljeni server:</span>{" "}
          auto-sinhronizacija čita samo browser profil istog Windows korisnika na tom serveru. Ako je server u Kanadi,
          regionalni servisi mogu odbiti prijavu, manifest ili licencu zbog IP lokacije; koristite ručni uvoz sesije,
          sniffer/bookmarklet ili pokrenite pristup iz regiona gde nalog ima pravo gledanja.
        </div>

        <SessionConsoleScriptHint service={importService} />

        <p className="text-[11px] text-indigo-300/90 m-0">
          Konzola skripte sada šalju token <strong>direktno u app</strong> (fetch → bridge). Bookmarklet iznad radi isto bez F12.
          Ručni paste u polje ispod je i dalje podržan.
        </p>

        <div className="flex flex-col gap-4">
          <div>
            <label>Izaberite servis</label>
            <CustomSelect
              value={importService}
              options={["voyo", "hrti", "rtsplaneta", "hbomax", "skyshowtime", "eon"]}
              onChange={(val) => setImportService(val)}
              formatLabel={(val) => {
                if (val === "voyo") return "Voyo";
                if (val === "hrti") return "HRTi";
                if (val === "rtsplaneta") return "RTS Planeta";
                if (val === "hbomax") return "HBO Max";
                if (val === "skyshowtime") return "SkyShowtime (kolačići)";
                if (val === "eon") return "EON TV (kolačići)";
                return val;
              }}
              className="max-w-xs"
            />
          </div>

          <div>
            <label>Podaci o sesiji (Token / Cookie JSON string)</label>
            <textarea
              value={importSessionData}
              placeholder={SESSION_IMPORT_PLACEHOLDERS[importService] || "Nalepite kopirani token ili sesijski JSON ovde…"}
              onChange={(e) => setImportSessionData(e.target.value)}
              rows={5}
              className="py-2.5 px-3 bg-black/40 border border-glass text-white rounded focus:outline-none w-full font-mono text-xs"
            />
          </div>

          <button
            onClick={handleImportSession}
            disabled={importLoading || !importSessionData.trim()}
            className="btn btn-premium-primary self-end gap-2"
            style={cssVars({
              "--btn-grad-start": "#fbbf24",
              "--btn-grad-end": "#d97706",
              "--btn-glow": "rgba(251,191,36,0.25)",
              "--btn-glow-hover": "rgba(251,191,36,0.45)"
            })}
          >
            {importLoading ? (
              <>
                <Loader2 className="w-5 h-5 animate-spin" />
                Uvoz u toku…
              </>
            ) : (
              <>
                <Download className="w-5 h-5" />
                Uvezi sesiju
              </>
            )}
          </button>
        </div>
      </div>

      {/* DevTools WebSocket Sniffer Proxy Panel */}
      <div id="settings-sniffer" className="glass-panel p-8 rounded-xl border border-glass flex flex-col gap-6 glow-cyan-card glow-card-premium scroll-mt-24">
        <h3 className="font-extrabold text-xl text-cyan-400 flex items-center gap-2">
          <Zap className="w-5 h-5 text-cyan-400 animate-pulse" />
          Tampermonkey Bridge v2 (Sesije + Sniffer)
        </h3>
        <p className="text-sm text-text-secondary leading-relaxed m-0">
          Instalirajte skriptu jednom — ona <strong>automatski šalje sesije</strong> u aplikaciju (bez F12 i copy-paste)
          i snifuje <strong>.mpd / license</strong> URL-ove tokom gledanja.
          Kada su oba spremna, preuzimanje može krenuti <strong>automatski</strong>.
        </p>

        <label className="flex items-center gap-3 cursor-pointer select-none">
          <input
            type="checkbox"
            checked={snifferAutoDownload}
            onChange={(e) => saveSnifferAutoDownload(e.target.checked)}
            className="w-4 h-4 accent-emerald-500"
          />
          <span className="text-sm text-white font-semibold">
            Auto-preuzimanje kad sniffer uhvati manifest + license
          </span>
        </label>

        <div className="bg-cyan-500/10 border border-cyan-500/30 rounded-lg p-6 flex flex-col gap-3">
          <div className="font-extrabold text-cyan-400 flex items-center gap-2 text-sm">
            <Sparkles className="w-4 h-4 text-cyan-400 animate-pulse" />
            Instalacija (~30 sekundi)
          </div>
          <ol className="list-decimal pl-5 flex flex-col gap-2 text-xs text-text-secondary m-0 leading-relaxed">
            <li>Instalirajte <strong>Tampermonkey</strong> ili <strong>Violentmonkey</strong>.</li>
            <li>
              Otvorite{" "}
              <a href={USERSCRIPT_INSTALL_URL} target="_blank" rel="noreferrer" className="text-cyan-300 underline font-mono">
                {USERSCRIPT_INSTALL_URL}
              </a>{" "}
              — Tampermonkey će ponuditi instalaciju (ili kopirajte kod ispod).
            </li>
            <li>Pokrenite <code className="font-mono bg-white/10 px-1 rounded">python run.py</code> i otvorite bilo koji servis — sesija se šalje sama.</li>
          </ol>
        </div>

        <div className="flex flex-col gap-2">
          <div className="flex items-center justify-between flex-wrap gap-2">
            <span className="text-xs font-bold text-white">Userscript (serviran sa backend-a):</span>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={async () => {
                  try {
                    const text = userscriptPreview || (await fetchUserscriptText());
                    await navigator.clipboard.writeText(text);
                    setSnifferScriptCopied(true);
                    setTimeout(() => setSnifferScriptCopied(false), 2000);
                  } catch {
                    showToast("Nije moguće učitati skriptu — pokrenite backend.", "error");
                  }
                }}
                className="btn btn-premium-secondary gap-1.5 py-1 px-3 text-xs"
              >
                {snifferScriptCopied ? <><Check className="w-3.5 h-3.5" /> Kopirano!</> : <><Copy className="w-3.5 h-3.5" /> Kopiraj skriptu</>}
              </button>
              <a
                href={USERSCRIPT_INSTALL_URL}
                target="_blank"
                rel="noreferrer"
                className="btn btn-premium-primary gap-1.5 py-1 px-3 text-xs no-underline"
              >
                Otvori za instalaciju
              </a>
            </div>
          </div>
          <textarea
            readOnly
            value={userscriptPreview || "// Učitava se sa /api/bridge/userscript.js ..."}
            className="input-premium font-mono text-[10px] bg-[#0d0e12]/80 h-32 resize-none"
            style={{ border: "1px solid rgba(6,182,212,0.2)" }}
          />
        </div>
      </div>

      <div id="settings-credentials" className="glass-panel p-8 rounded-xl border border-glass flex flex-col gap-6 glow-indigo-card glow-card-premium scroll-mt-24">
        <h3 className="font-extrabold text-xl text-indigo-400 border-b border-white/[0.04] pb-3">Upravljanje Kredencijalima</h3>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          
          {/* Voyo Login */}
          <div className="flex flex-col gap-4 p-6 rounded-lg bg-white/[0.02] border border-glass glow-orange-card glow-card-premium transition-all hover:bg-white/[0.03]">
            <h4 className="font-extrabold text-base text-white flex items-center gap-2 border-b border-white/[0.03] pb-2">
              <Tv className="w-4 h-4 service-voyo" />
              Voyo prijava
            </h4>
            <div>
              <label>Država / Region</label>
              <CustomSelect
                value={voyoVariant}
                options={["rs", "hr"]}
                onChange={(val) => setVoyoVariant(val)}
                formatLabel={(val) => val === "rs" ? "Srbija (Voyo.rs)" : "Hrvatska (Voyo.hr)"}
              />
            </div>
            <div>
              <label className="custom-checkbox-wrap cursor-pointer" style={{ marginTop: 4 }}>
                <input
                  type="checkbox"
                  checked={voyoIgnoreCatalogDrmHint}
                  onChange={(e) => {
                    const checked = e.target.checked;
                    setVoyoIgnoreCatalogDrmHint(checked);
                    void apiFetch("/api/config", {
                      method: "POST",
                      headers: { "Content-Type": "application/json" },
                      body: JSON.stringify({ voyo_ignore_catalog_drm_hint: checked }),
                    }).then(async (res) => {
                      if (res.ok) {
                        showToast("Voyo DRM podešavanje sačuvano.", "success");
                        await fetchStatus();
                      } else {
                        showToast("Greška pri čuvanju Voyo podešavanja.", "error");
                      }
                    });
                  }}
                />
                <div className={`custom-checkbox-box ${voyoIgnoreCatalogDrmHint ? "checked" : ""}`}>
                  <svg className="custom-checkbox-check" viewBox="0 0 10 10" fill="none" stroke="white" strokeWidth="2">
                    <polyline points="1.5 5 4 7.5 8.5 2" />
                  </svg>
                </div>
                <span className="text-sm font-semibold text-white">
                  Ignoriši DRM upozorenja iz kataloga
                </span>
              </label>
              <p style={{ fontSize: "0.68rem", color: "var(--text-muted)", marginTop: 4, marginLeft: 28 }}>
                Katalog ponekad lažno označava naslove — aplikacija ipak proverava stvarni stream (videoUrlV2).
                Uključite da podrazumevano označite i hint epizode.
              </p>
            </div>
            {status?.services?.voyo?.authenticated && voyoProfiles.length > 0 && (
              <div>
                <label>Korisnički profil</label>
                <CustomSelect
                  value={String(voyoActiveProfileId || voyoProfiles[0]?.profileId || "")}
                  options={voyoProfiles.map((p) => String(p.profileId))}
                  onChange={(val) => void selectVoyoProfile(Number(val))}
                  formatLabel={(val) => {
                    const p = voyoProfiles.find((x) => String(x.profileId) === val);
                    if (!p) return val;
                    const kind = p.type ? ` (${p.type})` : "";
                    return `${p.name}${kind}`;
                  }}
                />
                <p style={{ fontSize: "0.68rem", color: "var(--text-muted)", marginTop: 4 }}>
                  {voyoProfileSwitching ? "Menjam profil…" : "Kids i ostali profili sa Voyo naloga."}
                </p>
              </div>
            )}
            <div>
              <label>Email</label>
              <input type="email" value={voyoEmail} onChange={(e) => setVoyoEmail(e.target.value)} placeholder="email@voyo.rs" className="input-premium" style={cssVars({"--focused-border": "#f97316", "--focused-glow": "rgba(249,115,22,0.25)"})} />
            </div>
            <div>
              <label>Lozinka</label>
              <div className="password-wrapper">
                <input
                  type={showVoyoPass ? "text" : "password"}
                  value={voyoPassword}
                  onChange={(e) => setVoyoPassword(e.target.value)}
                  placeholder="••••••••"
                  className="input-premium pr-10"
                  style={cssVars({"--focused-border": "#f97316", "--focused-glow": "rgba(249,115,22,0.25)"})}
                />
                <button
                  type="button"
                  className="password-eye-btn"
                  onClick={() => setShowVoyoPass(!showVoyoPass)}
                >
                  {showVoyoPass ? (
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
            <SettingsCredentialFooter
              loginLabel="Prijavi se na Voyo"
              onLogin={() => submitLogin("voyo", { email: voyoEmail, password: voyoPassword, variant: voyoVariant })}
              onClear={() => void handleClearCredentials("voyo")}
              loginLoading={submittingLogin}
              clearLoading={clearingService === "voyo"}
              loginStyle={cssVars({
                "--btn-grad-start": "#f97316",
                "--btn-grad-end": "#ea580c",
                "--btn-glow": "rgba(249,115,22,0.25)",
                "--btn-glow-hover": "rgba(249,115,22,0.45)",
              })}
            />
          </div>

          {/* HRTi Credentials */}
          <div className="flex flex-col gap-4 p-6 rounded-lg bg-white/[0.02] border border-glass glow-cyan-card glow-card-premium transition-all hover:bg-white/[0.03]">
            <h4 className="font-extrabold text-base text-white flex items-center gap-2 border-b border-white/[0.03] pb-2">
              <Film className="w-4 h-4 service-hrti" />
              HRTi prijava
            </h4>
            <div>
              <label>Email</label>
              <input type="email" value={hrtiEmail} onChange={(e) => setHrtiEmail(e.target.value)} placeholder="email@hrti.hr" className="input-premium" style={cssVars({"--focused-border": "#06b6d4", "--focused-glow": "rgba(6,182,212,0.25)"})} />
            </div>
            <div>
              <label>Lozinka</label>
              <div className="password-wrapper">
                <input
                  type={showHrtiPass ? "text" : "password"}
                  value={hrtiPassword}
                  onChange={(e) => setHrtiPassword(e.target.value)}
                  placeholder="••••••••"
                  className="input-premium pr-10"
                  style={cssVars({"--focused-border": "#06b6d4", "--focused-glow": "rgba(6,182,212,0.25)"})}
                />
                <button
                  type="button"
                  className="password-eye-btn"
                  onClick={() => setShowHrtiPass(!showHrtiPass)}
                >
                  {showHrtiPass ? (
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
            <SettingsCredentialFooter
              loginLabel="Prijavi se na HRTi"
              onLogin={() => submitLogin("hrti", { email: hrtiEmail, password: hrtiPassword })}
              onClear={() => void handleClearCredentials("hrti")}
              loginLoading={submittingLogin}
              clearLoading={clearingService === "hrti"}
              loginStyle={cssVars({
                "--btn-grad-start": "#06b6d4",
                "--btn-grad-end": "#0284c7",
                "--btn-glow": "rgba(6,182,212,0.25)",
                "--btn-glow-hover": "rgba(6,182,212,0.45)",
              })}
            />
          </div>

          {/* EON device credentials */}
          <div className="flex flex-col gap-4 p-6 rounded-lg bg-white/[0.02] border border-glass lg:col-span-2 glow-green-card glow-card-premium transition-all hover:bg-white/[0.03]">
            <h4 className="font-extrabold text-base text-white flex items-center gap-2 border-b border-white/[0.03] pb-2">
              <Play className="w-4 h-4 service-eon" />
              EON TV - Uređaj i Nalog
            </h4>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label>EON Korisničko Ime (Email)</label>
                <input type="text" value={eonUsername} onChange={(e) => setEonUsername(e.target.value)} placeholder="npr. sbb_user@email.com" className="input-premium" style={cssVars({"--focused-border": "#10b981", "--focused-glow": "rgba(16,185,129,0.25)"})} />
              </div>
              <div>
                <label>Lozinka</label>
                <div className="password-wrapper">
                  <input
                    type={showEonPass ? "text" : "password"}
                    value={eonPassword}
                    onChange={(e) => setEonPassword(e.target.value)}
                    placeholder="••••••••"
                    className="input-premium pr-10"
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
              <div>
                <label>Device Serial (Serijski Broj)</label>
                <input type="text" value={eonSerial} onChange={(e) => setEonSerial(e.target.value)} placeholder="kopiraj iz payload-a" className="input-premium font-mono text-xs" style={cssVars({"--focused-border": "#10b981", "--focused-glow": "rgba(16,185,129,0.25)"})} />
                <p className="text-[10px] text-text-muted mt-1.5">Vrednost koju vidite kao device-serial u EON browser network payload-u.</p>
              </div>
              <div>
                <label>Device Number (Broj Uređaja)</label>
                <input type="text" value={eonNumber} onChange={(e) => setEonNumber(e.target.value)} placeholder="kopiraj iz response-a" className="input-premium font-mono text-xs" style={cssVars({"--focused-border": "#10b981", "--focused-glow": "rgba(16,185,129,0.25)"})} />
                <p className="text-[10px] text-text-muted mt-1.5">Vrednost koju vidite kao device-number u response-u.</p>
              </div>
            </div>
            <p className="text-[10px] text-text-muted border-t border-white/[0.04] pt-3 mt-1">
              Widevine <code className="font-mono bg-white/[0.04] px-1 rounded">device.wvd</code> podešavate u
              sekciji <strong className="text-violet-300">WVD / CDM</strong> iznad ili na DRM tabu.
              {deviceWvdInfo?.found ? " CDM fajl je pronađen ✓" : " CDM fajl trenutno nije pronađen ✗"}
            </p>
            <div className="mt-2 max-w-md">
              <SettingsCredentialFooter
                loginLabel={eonStatus?.engine_installed === false ? "EON engine nedostaje" : "Sačuvaj EON uređaj"}
                onLogin={() =>
                  submitLogin("eon", {
                    username: eonUsername,
                    password: eonPassword,
                    serial: eonSerial,
                    number: eonNumber,
                  })
                }
                onClear={() => void handleClearCredentials("eon")}
                loginLoading={submittingLogin}
                clearLoading={clearingService === "eon"}
                loginDisabled={eonStatus?.engine_installed === false}
                loginStyle={cssVars({
                  "--btn-grad-start": "#10b981",
                  "--btn-grad-end": "#059669",
                  "--btn-glow": "rgba(16,185,129,0.25)",
                  "--btn-glow-hover": "rgba(16,185,129,0.45)",
                })}
              />
            </div>
          </div>

          {/* RTS Planeta */}
          <div className="flex flex-col gap-4 p-6 rounded-lg bg-white/[0.02] border border-glass glow-rose-card glow-card-premium transition-all hover:bg-white/[0.03]">
            <h4 className="font-extrabold text-base text-white flex items-center gap-2 border-b border-white/[0.03] pb-2">
              <Radio className="w-4 h-4 service-rts" />
              RTS Planeta prijava
            </h4>
            <div>
              <label>Email</label>
              <input type="email" value={rtsEmail} onChange={(e) => setRtsEmail(e.target.value)} placeholder="email@rtsplaneta.rs" className="input-premium" style={cssVars({"--focused-border": "#f43f5e", "--focused-glow": "rgba(244,63,94,0.25)"})} />
            </div>
            <div>
              <label>Lozinka</label>
              <div className="password-wrapper">
                <input
                  type={showRtsPass ? "text" : "password"}
                  value={rtsPassword}
                  onChange={(e) => setRtsPassword(e.target.value)}
                  placeholder="••••••••"
                  className="input-premium pr-10"
                  style={cssVars({"--focused-border": "#f43f5e", "--focused-glow": "rgba(244,63,94,0.25)"})}
                />
                <button
                  type="button"
                  className="password-eye-btn"
                  onClick={() => setShowRtsPass(!showRtsPass)}
                >
                  {showRtsPass ? (
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
            <SettingsCredentialFooter
              loginLabel="Sačuvaj RTS kredencijale"
              onLogin={() => submitLogin("rts", { email: rtsEmail, password: rtsPassword })}
              onClear={() => void handleClearCredentials("rts")}
              loginLoading={submittingLogin}
              clearLoading={clearingService === "rts"}
              loginStyle={cssVars({
                "--btn-grad-start": "#f43f5e",
                "--btn-grad-end": "#e11d48",
                "--btn-glow": "rgba(244,63,94,0.25)",
                "--btn-glow-hover": "rgba(244,63,94,0.45)",
              })}
            />
          </div>

          {/* HBO Max */}
          <div className="flex flex-col gap-4 p-6 rounded-lg bg-white/[0.02] border border-glass glow-purple-card glow-card-premium transition-all hover:bg-white/[0.03]">
            <h4 className="font-extrabold text-base text-white flex items-center gap-2 border-b border-white/[0.03] pb-2">
              <Clapperboard className="w-4 h-4 service-hbo" />
              HBO Max
              {hboAuth?.authenticated && (
                <span className="text-[9px] font-bold text-emerald-400 ml-auto">Token aktivan</span>
              )}
            </h4>
            <p className="text-[10px] text-text-muted m-0 leading-relaxed">
              Prijava pokreće interaktivni device login u pozadini (pogledajte Logs). Alternativa: uvoz sesije iznad
              ili Max bookmarklet u sekciji Autentifikacija.
            </p>
            <div>
              <label>Tržište (market)</label>
              <CustomSelect
                value={hboMarket}
                options={["emea", "latam", "us"]}
                onChange={(val) => setHboMarket(val)}
                formatLabel={(val) => {
                  if (val === "emea") return "EMEA (Srbija / region)";
                  if (val === "latam") return "Latam";
                  if (val === "us") return "US";
                  return val;
                }}
                className="max-w-xs"
              />
            </div>
            <SettingsCredentialFooter
              loginLabel="Pokreni HBO Max prijavu"
              onLogin={() => void startHboLogin()}
              onClear={() => void handleClearCredentials("hbomax")}
              loginLoading={hboSubmitting}
              clearLoading={clearingService === "hbomax"}
              loginStyle={cssVars({
                "--btn-grad-start": "#9333ea",
                "--btn-grad-end": "#7e22ce",
                "--btn-glow": "rgba(147,51,234,0.25)",
                "--btn-glow-hover": "rgba(147,51,234,0.45)",
              })}
            />
          </div>

          {/* SkyShowtime */}
          <div className="flex flex-col gap-4 p-6 rounded-lg bg-white/[0.02] border border-glass glow-cyan-card glow-card-premium transition-all hover:bg-white/[0.03]">
            <h4 className="font-extrabold text-base text-white flex items-center gap-2 border-b border-white/[0.03] pb-2">
              <Tv className="w-4 h-4 text-cyan-400" />
              SkyShowtime
              {skyshowtimeAuth?.authenticated && (
                <span className="text-[9px] font-bold text-emerald-400 ml-auto">Sesija aktivna</span>
              )}
            </h4>
            <p className="text-[10px] text-text-muted m-0 leading-relaxed">
              Ulogujte se na skyshowtime.com u Chrome/Edge/Brave, zatvorite pretraživač i pokrenite sinhronizaciju.
              Alternativa: uvoz Netscape cookies.txt u sekciji Uvoz sesije.
            </p>
            <SettingsCredentialFooter
              loginLabel="Sinhronizuj iz pretraživača"
              onLogin={() => void startSkyshowtimeBrowserSync()}
              onClear={() => void handleClearCredentials("skyshowtime")}
              loginLoading={skyshowtimeSubmitting}
              clearLoading={clearingService === "skyshowtime"}
              loginStyle={cssVars({
                "--btn-grad-start": "#06b6d4",
                "--btn-grad-end": "#0891b2",
                "--btn-glow": "rgba(6,182,212,0.25)",
                "--btn-glow-hover": "rgba(6,182,212,0.45)",
              })}
            />
          </div>

        </div>
      </div>

    </div>
  </div>
  );
}
