import { useCallback, useRef, useState } from "react";
import { apiFetch, getStoredApiKey, parseApiError } from "../../lib/api";
import { errorMessage } from "../../utils/logUtils";
import type { AppStatus, TranscodeDiagnostics } from "../../types/app";
import type { ShowToastFn } from "../domainTypes";
import { useActionGuard } from "../useActionGuard";

export interface UseAppConfigOptions {
  showToast: ShowToastFn;
}

export function useAppConfig({ showToast }: UseAppConfigOptions) {
  const statusListenersRef = useRef(new Set<(data: AppStatus) => void>());
  const [status, setStatus] = useState<AppStatus | null>(null);
  const [outputDir, setOutputDir] = useState("");
  const [transcodeMode, setTranscodeMode] = useState("off");
  const [transcodeDiagnostics, setTranscodeDiagnostics] = useState<TranscodeDiagnostics | null>(null);
  const [binariesPaths, setBinariesPaths] = useState<Record<string, string>>({
    ffmpeg: "",
    mkvmerge: "",
    mp4decrypt: "",
    aria2c: "",
    device_wvd: "",
  });
  const [saveFeedback, setSaveFeedback] = useState(false);
  const [apiKeyInput, setApiKeyInput] = useState(getStoredApiKey);
  const [importService, setImportService] = useState("voyo");
  const [importSessionData, setImportSessionData] = useState("");
  const [importLoading, setImportLoading] = useState(false);
  const [autoSyncLoading, setAutoSyncLoading] = useState(false);
  const [ytdlpUpdating, setYtdlpUpdating] = useState(false);
  const [selectingOutputDir, setSelectingOutputDir] = useState(false);
  const [ytdlpNameTemplate, setYtdlpNameTemplate] = useState("%(title)s.%(ext)s");
  const [maxConcurrentDownloads, setMaxConcurrentDownloads] = useState(2);
  const [voyoIgnoreCatalogDrmHint, setVoyoIgnoreCatalogDrmHint] = useState(false);
  const [outputFormat, setOutputFormat] = useState("mp4");

  const deviceWvdInfo = status?.binaries?.device_wvd;

  const subscribeStatusLoaded = useCallback((listener: (data: AppStatus) => void) => {
    statusListenersRef.current.add(listener);
    return () => {
      statusListenersRef.current.delete(listener);
    };
  }, []);

  const fetchStatus = useCallback(async () => {
    try {
      const res = await apiFetch("/api/status");
      if (res.ok) {
        const data: AppStatus = await res.json();
        setStatus(data);
        setOutputDir(data.output_dir);
        if (data.transcode_mode) {
          setTranscodeMode(data.transcode_mode);
        }
        if (data.ytdlp_name_template) {
          setYtdlpNameTemplate(data.ytdlp_name_template);
        }
        if (data.max_concurrent_downloads) {
          setMaxConcurrentDownloads(data.max_concurrent_downloads);
        }
        if (data.output_format) {
          setOutputFormat(data.output_format);
        }
        setVoyoIgnoreCatalogDrmHint(data.voyo_ignore_catalog_drm_hint === true);
        const paths: Record<string, string> = {};
        for (const [name, info] of Object.entries(data.binaries)) {
          paths[name] = info.path;
        }
        setBinariesPaths(paths);
        for (const listener of statusListenersRef.current) {
          listener(data);
        }
      } else {
        showToast(await parseApiError(res, "Status servera nije dostupan."), "error");
      }
    } catch (e) {
      console.error("Failed to fetch system status:", e);
      showToast(errorMessage(e, "Ne mogu učitati status servera."), "error");
    }
  }, [showToast]);

  const fetchTranscodeDiagnostics = useCallback(async () => {
    try {
      const res = await apiFetch(`/api/transcoder/diagnose`);
      if (res.ok) {
        const data = await res.json();
        setTranscodeDiagnostics(data);
      }
    } catch (e) {
      console.error("Failed to fetch transcode diagnostics:", e);
    }
  }, []);

  const handleImportSession = useCallback(async () => {
    if (!importSessionData.trim()) {
      showToast("Nalepite podatke sesije pre uvoza.", "error");
      return;
    }
    setImportLoading(true);
    try {
      const res = await apiFetch(`/api/config/import-session`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          service: importService,
          session_data: importSessionData,
        }),
      });
      const data = await res.json();
      if (res.ok) {
        const msg = data.batch && data.imported?.length
          ? `${data.message}: ${data.imported.map((x: { service: string }) => x.service).join(", ")}`
          : data.message || "Sesija uspešno uvezena!";
        showToast(msg, "success");
        setImportSessionData("");
        await fetchStatus();
      } else {
        showToast(await parseApiError(res, "Greška pri uvozu sesije."), "error");
      }
    } catch (e) {
      showToast(errorMessage(e, "Greška na serveru"), "error");
    } finally {
      setImportLoading(false);
    }
  }, [fetchStatus, importService, importSessionData, showToast]);

  const handleAutoSyncBrowser = useCallback(async () => {
    setAutoSyncLoading(true);
    try {
      const res = await apiFetch(`/api/config/auto-sync-browser`, { method: "POST" });
      const data = await res.json();
      if (res.ok) {
        if (data.unsupported_platform) {
          showToast(data.message || "Sinhronizacija nije podržana na ovom sistemu.", "error");
        } else if (data.synced_any) {
          showToast(data.message || "Sinhronizacija sesija završena.", "success");
        } else {
          showToast(
            data.message ||
              "Nisu pronađene aktivne sesije. Proverite da li ste ulogovani u pretraživačima i zatvorite ih ako su zaključani.",
            data.browser_locked ? "error" : "info",
          );
        }
        await fetchStatus();
      } else {
        showToast(await parseApiError(res, "Greška pri sinhronizaciji."), "error");
      }
    } catch (e: unknown) {
      showToast(errorMessage(e, "Greška na serveru"), "error");
    } finally {
      setAutoSyncLoading(false);
    }
  }, [fetchStatus, showToast]);

  const handleSaveConfig = useCallback(async () => {
    try {
      const res = await apiFetch(`/api/config`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          output_dir: outputDir,
          transcode_mode: transcodeMode,
          binaries: binariesPaths,
          ytdlp_name_template: ytdlpNameTemplate,
          max_concurrent_downloads: maxConcurrentDownloads,
          voyo_ignore_catalog_drm_hint: voyoIgnoreCatalogDrmHint,
          output_format: outputFormat,
        }),
      });
      if (res.ok) {
        showToast("Podešavanja uspešno sačuvana!", "success");
        setSaveFeedback(true);
        setTimeout(() => setSaveFeedback(false), 2500);
        await fetchStatus();
        void fetchTranscodeDiagnostics();
      } else {
        showToast(await parseApiError(res, "Greška pri čuvanju podešavanja."), "error");
      }
    } catch (e: unknown) {
      showToast(errorMessage(e, "Greška na serveru"), "error");
    }
  }, [binariesPaths, fetchStatus, fetchTranscodeDiagnostics, maxConcurrentDownloads, outputDir, showToast, transcodeMode, voyoIgnoreCatalogDrmHint, ytdlpNameTemplate, outputFormat]);

  const selectOutputFolder = useCallback(async () => {
    setSelectingOutputDir(true);
    try {
      const res = await apiFetch(`/api/config/select-output-folder`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ initial_dir: outputDir }),
        timeoutMs: 610_000,
      });
      if (res.ok) {
        const data = await res.json();
        if (data.cancelled) {
          showToast("Izbor foldera je otkazan.", "info");
          return;
        }
        const selected = data.output_dir || outputDir;
        setOutputDir(selected);
        showToast("Output folder je izabran i sačuvan.", "success");
        await fetchStatus();
      } else {
        showToast(await parseApiError(res, "Ne mogu otvoriti izbor foldera."), "error");
      }
    } catch (e: unknown) {
      showToast(errorMessage(e, "Greška pri izboru foldera"), "error");
    } finally {
      setSelectingOutputDir(false);
    }
  }, [fetchStatus, outputDir, showToast]);

  const handleSaveDeviceWvdPath = useCallback(async () => {
    try {
      const res = await apiFetch(`/api/config`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ binaries: { device_wvd: binariesPaths.device_wvd || "" } }),
      });
      if (res.ok) {
        showToast("Putanja do device.wvd je sačuvana; CDM je osvežen.", "success");
        await fetchStatus();
        try {
          await apiFetch("/api/drm/reload", { method: "POST" });
        } catch {
          /* config POST already reloads CDM on backend */
        }
      } else {
        showToast(await parseApiError(res, "Greška pri čuvanju device.wvd putanje."), "error");
      }
    } catch (e: unknown) {
      showToast(errorMessage(e, "Greska na serveru"), "error");
    }
  }, [binariesPaths.device_wvd, fetchStatus, showToast]);

  const submitLogin = useCallback(
    async (service: string, body: Record<string, unknown>) => {
      try {
        const res = await apiFetch(`/api/${service}/login`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        });
        const data = await res.json();
        if (res.ok) {
          showToast(`Kredencijali za ${service.toUpperCase()} uspešno sačuvani!`, "success");
          if (data.warning) {
            showToast(data.warning, "info");
          }
          await fetchStatus();
        } else {
          showToast(await parseApiError(res, data.detail || "Greška pri prijavi."), "error");
        }
      } catch (e: unknown) {
        showToast(errorMessage(e, "Greška na serveru"), "error");
      }
    },
    [fetchStatus, showToast],
  );

  const openOutputFolder = useCallback(async () => {
    try {
      const res = await apiFetch("/api/open-output-folder", { method: "POST" });
      if (res.ok) {
        showToast("Output folder otvoren u Explorer-u.", "success");
      } else {
        showToast(await parseApiError(res, "Ne mogu otvoriti folder."), "error");
      }
    } catch (e: unknown) {
      showToast(errorMessage(e, "Greška na serveru"), "error");
    }
  }, [showToast]);

  const [clearingService, setClearingService] = useState<string | null>(null);
  const [savingApiKey, setSavingApiKey] = useState(false);
  const [migratingCredentials, setMigratingCredentials] = useState(false);

  const handleClearCredentials = useCallback(
    async (service: string): Promise<boolean> => {
      setClearingService(service);
      try {
        const res = await apiFetch("/api/credentials/clear", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ service }),
        });
        if (res.ok) {
          const data = await res.json();
          showToast(data.message || "Kredencijali obrisani.", "success");
          await fetchStatus();
          return true;
        }
        showToast(await parseApiError(res, "Greška pri brisanju kredencijala."), "error");
        return false;
      } catch (e: unknown) {
        showToast(errorMessage(e, "Greška na serveru"), "error");
        return false;
      } finally {
        setClearingService(null);
      }
    },
    [fetchStatus, showToast],
  );

  const handleMigrateCredentials = useCallback(async () => {
    setMigratingCredentials(true);
    try {
      const res = await apiFetch("/api/credentials/migrate", { method: "POST" });
      if (res.ok) {
        const data = await res.json();
        const migrated = (data.report?.migrated as string[] | undefined)?.length ?? 0;
        const native = (data.report?.native as string[] | undefined)?.length ?? 0;
        const legacy = (data.legacy_moved as string[] | undefined)?.length ?? 0;
        const total = migrated + native + legacy;
        showToast(
          total > 0
            ? `Migracija završena (${total} polja prebačeno u keyring).`
            : "Nema plaintext tajni za migraciju — sve je već u keyring-u.",
          total > 0 ? "success" : "info",
        );
        await fetchStatus();
      } else {
        showToast(await parseApiError(res, "Greška pri migraciji kredencijala."), "error");
      }
    } catch (e: unknown) {
      showToast(errorMessage(e, "Greška na serveru"), "error");
    } finally {
      setMigratingCredentials(false);
    }
  }, [fetchStatus, showToast]);

  const handleSaveApiKeyToServer = useCallback(async () => {
    const key = apiKeyInput.trim();
    if (!key) {
      showToast("Unesite API ključ pre čuvanja na server.", "error");
      return;
    }
    setSavingApiKey(true);
    try {
      const res = await apiFetch("/api/config/api-key", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ api_key: key }),
      });
      if (res.ok) {
        showToast("API ključ sačuvan na serveru (config.json).", "success");
        await fetchStatus();
      } else {
        showToast(await parseApiError(res, "Greška pri čuvanju API ključa."), "error");
      }
    } catch (e: unknown) {
      showToast(errorMessage(e, "Greška na serveru"), "error");
    } finally {
      setSavingApiKey(false);
    }
  }, [apiKeyInput, fetchStatus, showToast]);

  const handleUpdateYtdlp = useCallback(async () => {
    setYtdlpUpdating(true);
    showToast("Ažuriranje yt-dlp alata je započeto...", "info");
    try {
      const res = await apiFetch(`/api/system/update-ytdlp`, { method: "POST" });
      const data = await res.json();
      if (res.ok && data.success) {
        showToast(data.message || "yt-dlp je uspešno ažuriran!", "success");
      } else {
        showToast(data.message || "Ažuriranje yt-dlp-a nije uspelo.", "error");
      }
      await fetchStatus();
    } catch (e: unknown) {
      showToast(errorMessage(e, "Greška na serveru"), "error");
    } finally {
      setYtdlpUpdating(false);
    }
  }, [fetchStatus, showToast]);

  const [guardedSaveConfig, savingConfig] = useActionGuard(handleSaveConfig);
  const [guardedSubmitLogin, submittingLogin] = useActionGuard(submitLogin);

  return {
    status,
    setStatus,
    outputDir,
    setOutputDir,
    transcodeMode,
    setTranscodeMode,
    transcodeDiagnostics,
    setTranscodeDiagnostics,
    binariesPaths,
    setBinariesPaths,
    saveFeedback,
    setSaveFeedback,
    apiKeyInput,
    setApiKeyInput,
    importService,
    setImportService,
    importSessionData,
    setImportSessionData,
    importLoading,
    setImportLoading,
    autoSyncLoading,
    setAutoSyncLoading,
    ytdlpUpdating,
    handleUpdateYtdlp,
    selectingOutputDir,
    selectOutputFolder,
    ytdlpNameTemplate,
    setYtdlpNameTemplate,
    maxConcurrentDownloads,
    setMaxConcurrentDownloads,
    voyoIgnoreCatalogDrmHint,
    setVoyoIgnoreCatalogDrmHint,
    outputFormat,
    setOutputFormat,
    deviceWvdInfo,
    fetchStatus,
    subscribeStatusLoaded,
    fetchTranscodeDiagnostics,
    handleImportSession,
    handleAutoSyncBrowser,
    handleSaveConfig: guardedSaveConfig,
    savingConfig,
    handleSaveDeviceWvdPath,
    handleClearCredentials,
    clearingService,
    handleSaveApiKeyToServer,
    savingApiKey,
    handleMigrateCredentials,
    migratingCredentials,
    submitLogin: guardedSubmitLogin,
    submittingLogin,
    openOutputFolder,
  };
}

export type AppConfigSlice = ReturnType<typeof useAppConfig>;
