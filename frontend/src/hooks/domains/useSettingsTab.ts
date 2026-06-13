import { useCallback } from "react";
import { useAppConfigSlice, useAppShellSlice, useHboSlice, useSkyshowtimeSlice, useSnifferSlice } from "../../context/appStore";
import { useCredentials } from "./useCredentials";
import { useVoyoProfiles } from "./useVoyoProfiles";

const CLEAR_SERVICE_LABELS: Record<string, string> = {
  voyo: "Voyo",
  hrti: "HRTi",
  rts: "RTS Planeta",
  eon: "EON TV",
  hbomax: "HBO Max",
  skyshowtime: "SkyShowtime",
};

const CLEAR_FIELD_MAP: Record<string, (c: ReturnType<typeof useCredentials>) => void> = {
  voyo: (c) => {
    c.setVoyoEmail("");
    c.setVoyoPassword("");
  },
  hrti: (c) => {
    c.setHrtiEmail("");
    c.setHrtiPassword("");
  },
  rts: (c) => {
    c.setRtsEmail("");
    c.setRtsPassword("");
  },
  eon: (c) => {
    c.setEonUsername("");
    c.setEonPassword("");
    c.setEonSerial("");
    c.setEonNumber("");
  },
};

/** Settings tab: global config, sniffer tools, and service credentials. */
export function useSettingsTab() {
  const config = useAppConfigSlice();
  const sniffer = useSnifferSlice();
  const credentials = useCredentials();
  const hbo = useHboSlice();
  const skyshowtime = useSkyshowtimeSlice();
  const { showToast, setActiveTab } = useAppShellSlice();
  const voyoAuthenticated = config.status?.services?.voyo?.authenticated === true;
  const voyoProfiles = useVoyoProfiles(voyoAuthenticated, showToast);

  const handleClearCredentials = useCallback(
    async (service: string) => {
      const label = CLEAR_SERVICE_LABELS[service] || service;
      if (!window.confirm(`Obrisati sve sačuvane kredencijale za ${label}?`)) {
        return;
      }
      const ok = await config.handleClearCredentials(service);
      if (!ok) return;
      CLEAR_FIELD_MAP[service]?.(credentials);
      if (service === "hbomax") {
        hbo.setHboMarket("emea");
        hbo.refreshAuth();
      }
      if (service === "skyshowtime") {
        skyshowtime.refreshAuth();
      }
    },
    [config, credentials, hbo, skyshowtime],
  );

  return {
    setActiveTab,
    browserSyncSupported: config.status?.browser_sync_supported !== false,
    apiKeyInput: config.apiKeyInput,
    setApiKeyInput: config.setApiKeyInput,
    autoSyncLoading: config.autoSyncLoading,
    ytdlpUpdating: config.ytdlpUpdating,
    handleUpdateYtdlp: config.handleUpdateYtdlp,
    binariesPaths: config.binariesPaths,
    setBinariesPaths: config.setBinariesPaths,
    deviceWvdInfo: config.deviceWvdInfo,
    fetchStatus: config.fetchStatus,
    fetchTranscodeDiagnostics: config.fetchTranscodeDiagnostics,
    handleAutoSyncBrowser: config.handleAutoSyncBrowser,
    handleImportSession: config.handleImportSession,
    handleSaveConfig: config.handleSaveConfig,
    savingConfig: config.savingConfig,
    submittingLogin: config.submittingLogin,
    handleClearCredentials,
    clearingService: config.clearingService,
    handleSaveApiKeyToServer: config.handleSaveApiKeyToServer,
    savingApiKey: config.savingApiKey,
    handleMigrateCredentials: config.handleMigrateCredentials,
    migratingCredentials: config.migratingCredentials,
    handleSaveDeviceWvdPath: config.handleSaveDeviceWvdPath,
    importLoading: config.importLoading,
    importService: config.importService,
    setImportService: config.setImportService,
    importSessionData: config.importSessionData,
    setImportSessionData: config.setImportSessionData,
    openOutputFolder: config.openOutputFolder,
    outputDir: config.outputDir,
    setOutputDir: config.setOutputDir,
    selectingOutputDir: config.selectingOutputDir,
    selectOutputFolder: config.selectOutputFolder,
    saveFeedback: config.saveFeedback,
    status: config.status,
    submitLogin: config.submitLogin,
    transcodeDiagnostics: config.transcodeDiagnostics,
    transcodeMode: config.transcodeMode,
    setTranscodeMode: config.setTranscodeMode,
    ytdlpNameTemplate: config.ytdlpNameTemplate,
    setYtdlpNameTemplate: config.setYtdlpNameTemplate,
    maxConcurrentDownloads: config.maxConcurrentDownloads,
    setMaxConcurrentDownloads: config.setMaxConcurrentDownloads,
    voyoIgnoreCatalogDrmHint: config.voyoIgnoreCatalogDrmHint,
    setVoyoIgnoreCatalogDrmHint: config.setVoyoIgnoreCatalogDrmHint,
    outputFormat: config.outputFormat,
    setOutputFormat: config.setOutputFormat,
    snifferAutoDownload: sniffer.snifferAutoDownload,
    saveSnifferAutoDownload: sniffer.saveSnifferAutoDownload,
    userscriptPreview: sniffer.userscriptPreview,
    snifferScriptCopied: sniffer.snifferScriptCopied,
    setSnifferScriptCopied: sniffer.setSnifferScriptCopied,
    showToast,
    hboMarket: hbo.hboMarket,
    setHboMarket: hbo.setHboMarket,
    startHboLogin: hbo.startHboLogin,
    hboSubmitting: hbo.hboSubmitting,
    hboAuth: hbo.hboAuth,
    refreshHboAuth: hbo.refreshAuth,
    skyshowtimeAuth: skyshowtime.skyshowtimeAuth,
    refreshSkyshowtimeAuth: skyshowtime.refreshAuth,
    startSkyshowtimeBrowserSync: skyshowtime.startSkyshowtimeBrowserSync,
    skyshowtimeSubmitting: skyshowtime.skyshowtimeSubmitting,
    ...credentials,
    ...voyoProfiles,
  };
}

export type SettingsTabSlice = ReturnType<typeof useSettingsTab>;
