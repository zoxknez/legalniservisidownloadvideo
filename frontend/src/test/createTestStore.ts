import { createRef } from "react";
import type { AppStore, AppShellSlice } from "../context/appStore";
import type { AppConfigSlice } from "../hooks/domains/useAppConfig";
import type { DownloadQueueSlice } from "../hooks/domains/useDownloadQueue";
import type { EonSlice } from "../hooks/domains/useEon";
import type { HboSlice } from "../hooks/domains/useHbo";
import type { HrtiSlice } from "../hooks/domains/useHrti";
import type { RtsSlice } from "../hooks/domains/useRts";
import type { SmartDashboardSlice } from "../hooks/domains/useSmartDashboard";
import type { SnifferSlice } from "../hooks/domains/useSniffer";
import type { VoyoSlice } from "../hooks/domains/useVoyo";
import type { AppStatus } from "../types/app";

const noop = () => {};
const noopAsync = async () => {};

export const mockAppStatus: AppStatus = {
  output_dir: "/tmp/out",
  transcode_mode: "off",
  binaries: {
    ffmpeg: { found: true, path: "/usr/bin/ffmpeg" },
    mkvmerge: { found: false, path: "" },
    mp4decrypt: { found: false, path: "" },
    aria2c: { found: false, path: "" },
    device_wvd: { found: false, path: "" },
  },
  sniffer: { auto_download: true },
  services: {
    voyo: { authenticated: false },
    hrti: { authenticated: false },
    rts: { authenticated: false },
    eon: { authenticated: false },
    hbo: { authenticated: false },
  },
};

function shellSlice(overrides: Partial<AppShellSlice> = {}): AppShellSlice {
  return {
    activeTab: "dashboard",
    setActiveTab: noop,
    toast: null,
    toastKey: 0,
    setToast: noop,
    setToastKey: noop,
    showToast: vi.fn(),
    ...overrides,
  };
}

function configSlice(overrides: Partial<AppConfigSlice> = {}): AppConfigSlice {
  return {
    status: mockAppStatus,
    setStatus: noop,
    outputDir: "/tmp/out",
    setOutputDir: noop,
    transcodeMode: "off",
    setTranscodeMode: noop,
    transcodeDiagnostics: null,
    setTranscodeDiagnostics: noop,
    binariesPaths: { ffmpeg: "/usr/bin/ffmpeg", mkvmerge: "", mp4decrypt: "", aria2c: "", device_wvd: "" },
    setBinariesPaths: noop,
    saveFeedback: false,
    setSaveFeedback: noop,
    apiKeyInput: "",
    setApiKeyInput: noop,
    importService: "voyo",
    setImportService: noop,
    importSessionData: "",
    setImportSessionData: noop,
    importLoading: false,
    setImportLoading: noop,
    autoSyncLoading: false,
    setAutoSyncLoading: noop,
    ytdlpUpdating: false,
    handleUpdateYtdlp: noopAsync,
    ytdlpNameTemplate: "%(title)s.%(ext)s",
    setYtdlpNameTemplate: noop,
    maxConcurrentDownloads: 2,
    setMaxConcurrentDownloads: noop,
    deviceWvdInfo: mockAppStatus.binaries.device_wvd,
    fetchStatus: noopAsync,
    subscribeStatusLoaded: () => noop,
    fetchTranscodeDiagnostics: noopAsync,
    handleImportSession: noopAsync,
    handleAutoSyncBrowser: noopAsync,
    handleSaveConfig: noopAsync,
    savingConfig: false,
    handleSaveDeviceWvdPath: noopAsync,
    handleClearCredentials: async () => false,
    clearingService: null,
    handleSaveApiKeyToServer: noopAsync,
    savingApiKey: false,
    handleMigrateCredentials: noopAsync,
    migratingCredentials: false,
    submitLogin: noopAsync,
    submittingLogin: false,
    openOutputFolder: noopAsync,
    ...overrides,
  };
}

function queueSlice(overrides: Partial<DownloadQueueSlice> = {}): DownloadQueueSlice {
  return {
    downloads: [],
    setDownloads: noop,
    connected: false,
    setConnected: noop,
    scheduledTasks: [],
    setScheduledTasks: noop,
    confirmClear: false,
    setConfirmClear: noop,
    showLogModal: false,
    setShowLogModal: noop,
    selectedTask: null,
    setSelectedTask: noop,
    selectedTaskRef: createRef(),
    logEndRef: createRef(),
    logCopied: false,
    setLogCopied: noop,
    logFullscreen: false,
    setLogFullscreen: noop,
    activeDownloadsCount: 0,
    fetchScheduledRecordings: noopAsync,
    cancelDownloadTask: noopAsync,
    retryDownloadTask: noopAsync,
    clearCompletedQueue: noopAsync,
    ...overrides,
  };
}

function voyoSlice(overrides: Partial<VoyoSlice> = {}): VoyoSlice {
  return {
    voyoEmail: "user@voyo.test",
    setVoyoEmail: noop,
    voyoPassword: "secret",
    setVoyoPassword: noop,
    showVoyoPass: false,
    setShowVoyoPass: noop,
    voyoMode: "video",
    setVoyoMode: noop,
    voyoTarget: "",
    setVoyoTarget: noop,
    voyoRes: "1080p",
    setVoyoRes: noop,
    voyoSeriesData: null,
    setVoyoSeriesData: noop,
    voyoSearching: false,
    setVoyoSearching: noop,
    selectedVoyoEpisodes: [],
    setSelectedVoyoEpisodes: noop,
    voyoEpisodesRange: "",
    setVoyoEpisodesRange: noop,
    voyoSubmitting: false,
    searchVoyoSeries: noopAsync,
    startVoyoDownload: noopAsync,
    ...overrides,
  } as VoyoSlice;
}

function hrtiSlice(overrides: Partial<HrtiSlice> = {}): HrtiSlice {
  return {
    hrtiEmail: "",
    setHrtiEmail: noop,
    hrtiPassword: "",
    setHrtiPassword: noop,
    showHrtiPass: false,
    setShowHrtiPass: noop,
    hrtiModal: null,
    setHrtiModal: noop,
    hrtiModalTitle: "",
    setHrtiModalTitle: noop,
    hrtiCats: [],
    setHrtiCats: noop,
    selectedCat: "",
    setSelectedCat: noop,
    catItems: [],
    setCatItems: noop,
    catPage: 1,
    setCatPage: noop,
    catTotalPages: 1,
    setCatTotalPages: noop,
    hrtiSearchQuery: "",
    setHrtiSearchQuery: noop,
    hrtiLoadingItems: false,
    setHrtiLoadingItems: noop,
    hrtiDownloadWorkers: 1,
    selectedHrtiSeries: null,
    setSelectedHrtiSeries: noop,
    fetchHrtiCategories: noopAsync,
    fetchHrtiCategoryItems: noopAsync,
    searchHrti: noopAsync,
    fetchHrtiSeriesEpisodes: noopAsync,
    hrtiSubmitting: false,
    startHrtiDownload: noopAsync,
    confirmHrtiDownload: noopAsync,
    ...overrides,
  } as HrtiSlice;
}

function eonSlice(overrides: Partial<EonSlice> = {}): EonSlice {
  return {
    eonUsername: "",
    setEonUsername: noop,
    eonPassword: "",
    setEonPassword: noop,
    eonSerial: "",
    setEonSerial: noop,
    eonNumber: "",
    setEonNumber: noop,
    showEonPass: false,
    setShowEonPass: noop,
    eonMode: "vod",
    setEonMode: noop,
    eonLiveInputMode: "catalog",
    setEonLiveInputMode: noop,
    eonTarget: "",
    setEonTarget: noop,
    eonDuration: 3600,
    setEonDuration: noop,
    eonEpisodesRange: "",
    setEonEpisodesRange: noop,
    eonPlay: false,
    setEonPlay: noop,
    eonPlayerPath: "",
    setEonPlayerPath: noop,
    eonChannels: [],
    setEonChannels: noop,
    eonSearchQuery: "",
    setEonSearchQuery: noop,
    eonSearchResults: [],
    setEonSearchResults: noop,
    eonEpgItems: [],
    setEonEpgItems: noop,
    eonStatus: mockAppStatus.services.eon,
    eonReady: false,
    eonMissing: [],
    eonOptionalMissing: [],
    eonRootPath: "root aplikacije",
    eonCatalogPath: (name: string) => name,
    fetchEonChannels: noopAsync,
    fetchEonEpg: noopAsync,
    searchEonVod: noopAsync,
    startEonDownload: noopAsync,
    initEonCatalogs: noopAsync,
    loginEonApi: noopAsync,
    refreshEonApiToken: noopAsync,
    eonSubmitting: false,
    scheduleEonRecording: noopAsync,
    ...overrides,
  } as EonSlice;
}

function rtsSlice(overrides: Partial<RtsSlice> = {}): RtsSlice {
  return {
    rtsEmail: "",
    setRtsEmail: noop,
    rtsPassword: "",
    setRtsPassword: noop,
    showRtsPass: false,
    setShowRtsPass: noop,
    rtsTarget: "",
    setRtsTarget: noop,
    rtsStartEp: "",
    setRtsStartEp: noop,
    rtsEndEp: "",
    setRtsEndEp: noop,
    rtsVerbose: false,
    setRtsVerbose: noop,
    rtsVideoInfo: null,
    setRtsVideoInfo: noop,
    rtsInfoLoading: false,
    setRtsInfoLoading: noop,
    rtsSubmitting: false,
    fetchRtsVideoInfo: noopAsync,
    startRtsDownload: noopAsync,
    ...overrides,
  } as RtsSlice;
}

function hboSlice(overrides: Partial<HboSlice> = {}): HboSlice {
  return {
    hboMarket: "emea",
    setHboMarket: noop,
    hboTarget: "",
    setHboTarget: noop,
    hboSubs: "hr",
    setHboSubs: noop,
    hboDirectMode: false,
    setHboDirectMode: noop,
    hboManifestUrl: "",
    setHboManifestUrl: noop,
    hboLicenseUrl: "",
    setHboLicenseUrl: noop,
    hboDirectTitle: "",
    setHboDirectTitle: noop,
    hboDirectSubs: "hr",
    setHboDirectSubs: noop,
    hboSubmitting: false,
    hboAuth: null,
    refreshAuth: noop,
    startHboLogin: noopAsync,
    startHboDownload: noopAsync,
    startHboDirectDownload: noopAsync,
    ...overrides,
  } as HboSlice;
}

function smartSlice(overrides: Partial<SmartDashboardSlice> = {}): SmartDashboardSlice {
  return {
    smartUrl: "",
    setSmartUrl: noop,
    smartLoading: false,
    setSmartLoading: noop,
    smartData: null,
    setSmartData: noop,
    smartSelectedEpisodes: [],
    setSmartSelectedEpisodes: noop,
    smartEpisodesRange: "",
    setSmartEpisodesRange: noop,
    smartResolution: "1080p",
    setSmartResolution: noop,
    smartSubs: "sr",
    setSmartSubs: noop,
    smartRtsVerbose: false,
    setSmartRtsVerbose: noop,
    smartRtsStartEp: "",
    setSmartRtsStartEp: noop,
    smartRtsEndEp: "",
    setSmartRtsEndEp: noop,
    smartSubmitting: false,
    debouncedDetect: noop,
    smartAudioOnly: false,
    setSmartAudioOnly: noop,
    smartUseAria2: false,
    setSmartUseAria2: noop,
    ytdlpHardsub: false,
    setYtdlpHardsub: noop,
    ytdlpCookiesBrowser: "",
    setYtdlpCookiesBrowser: noop,
    ytdlpImpersonate: false,
    setYtdlpImpersonate: noop,
    ytdlpProxy: "",
    setYtdlpProxy: noop,
    ytdlpGeoBypass: false,
    setYtdlpGeoBypass: noop,
    ytdlpEmbedThumbnail: false,
    setYtdlpEmbedThumbnail: noop,
    ytdlpEmbedMetadata: false,
    setYtdlpEmbedMetadata: noop,
    ytdlpLimitRate: "",
    setYtdlpLimitRate: noop,
    handleSmartDetect: noopAsync,
    startSmartDownload: noopAsync,
    ...overrides,
  } as SmartDashboardSlice;
}

function snifferSlice(overrides: Partial<SnifferSlice> = {}): SnifferSlice {
  return {
    sniffedItems: {},
    setSniffedItems: noop,
    latestSniffed: null,
    setLatestSniffed: noop,
    showSnifferToast: false,
    setShowSnifferToast: noop,
    snifferScriptCopied: false,
    setSnifferScriptCopied: noop,
    userscriptPreview: "",
    setUserscriptPreview: noop,
    snifferAutoDownload: true,
    setSnifferAutoDownload: noop,
    snifferReady: {},
    setSnifferReady: noop,
    snifferDownloading: null,
    setSnifferDownloading: noop,
    fetchSnifferCaptures: noopAsync,
    applySniffedResource: noop,
    downloadSnifferCapture: noopAsync,
    saveSnifferAutoDownload: noopAsync,
    ...overrides,
  };
}

export type TestStoreOverrides = {
  shell?: Partial<AppShellSlice>;
  queue?: Partial<DownloadQueueSlice>;
  config?: Partial<AppConfigSlice>;
  voyo?: Partial<VoyoSlice>;
  hrti?: Partial<HrtiSlice>;
  eon?: Partial<EonSlice>;
  rts?: Partial<RtsSlice>;
  hbo?: Partial<HboSlice>;
  smart?: Partial<SmartDashboardSlice>;
  sniffer?: Partial<SnifferSlice>;
};

export function createTestStore(overrides: TestStoreOverrides = {}): AppStore {
  return {
    shell: shellSlice(overrides.shell),
    queue: queueSlice(overrides.queue),
    config: configSlice(overrides.config),
    voyo: voyoSlice(overrides.voyo),
    hrti: hrtiSlice(overrides.hrti),
    eon: eonSlice(overrides.eon),
    rts: rtsSlice(overrides.rts),
    hbo: hboSlice(overrides.hbo),
    smart: smartSlice(overrides.smart),
    sniffer: snifferSlice(overrides.sniffer),
  };
}
