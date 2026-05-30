import { useAppConfigSlice, useAppShellSlice, useSnifferSlice } from "../../context/appStore";
import { useCredentials } from "./useCredentials";

/** Settings tab: global config, sniffer tools, and service credentials. */
export function useSettingsTab() {
  const config = useAppConfigSlice();
  const sniffer = useSnifferSlice();
  const credentials = useCredentials();
  const { showToast } = useAppShellSlice();

  return {
    apiKeyInput: config.apiKeyInput,
    setApiKeyInput: config.setApiKeyInput,
    autoSyncLoading: config.autoSyncLoading,
    binariesPaths: config.binariesPaths,
    setBinariesPaths: config.setBinariesPaths,
    deviceWvdInfo: config.deviceWvdInfo,
    fetchStatus: config.fetchStatus,
    fetchTranscodeDiagnostics: config.fetchTranscodeDiagnostics,
    handleAutoSyncBrowser: config.handleAutoSyncBrowser,
    handleImportSession: config.handleImportSession,
    handleSaveConfig: config.handleSaveConfig,
    handleSaveDeviceWvdPath: config.handleSaveDeviceWvdPath,
    importLoading: config.importLoading,
    importService: config.importService,
    setImportService: config.setImportService,
    importSessionData: config.importSessionData,
    setImportSessionData: config.setImportSessionData,
    openOutputFolder: config.openOutputFolder,
    outputDir: config.outputDir,
    setOutputDir: config.setOutputDir,
    saveFeedback: config.saveFeedback,
    status: config.status,
    submitLogin: config.submitLogin,
    transcodeDiagnostics: config.transcodeDiagnostics,
    transcodeMode: config.transcodeMode,
    setTranscodeMode: config.setTranscodeMode,
    snifferAutoDownload: sniffer.snifferAutoDownload,
    saveSnifferAutoDownload: sniffer.saveSnifferAutoDownload,
    userscriptPreview: sniffer.userscriptPreview,
    snifferScriptCopied: sniffer.snifferScriptCopied,
    setSnifferScriptCopied: sniffer.setSnifferScriptCopied,
    showToast,
    ...credentials,
  };
}

export type SettingsTabSlice = ReturnType<typeof useSettingsTab>;
