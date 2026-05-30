import { useCallback, useRef, useState } from "react";
import { apiFetch, getStoredApiKey, parseApiError } from "../../lib/api";
import { errorMessage } from "../../utils/logUtils";
import type { AppStatus, TranscodeDiagnostics } from "../../types/app";
import type { ShowToastFn } from "../domainTypes";

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

  const deviceWvdInfo = status?.binaries.device_wvd;

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
        const paths: Record<string, string> = {};
        for (const [name, info] of Object.entries(data.binaries)) {
          paths[name] = info.path;
        }
        setBinariesPaths(paths);
        for (const listener of statusListenersRef.current) {
          listener(data);
        }
      }
    } catch (e) {
      console.error("Failed to fetch system status:", e);
    }
  }, []);

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
        showToast(data.detail || "Greška pri uvozu sesije.", "error");
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
        if (data.synced_any) {
          const successes = Object.entries(data.report || {})
            .filter(([, success]) => success)
            .map(([service]) =>
              service.replace(".rs", "").replace(".hrt.hr", "").replace(".tv", "").toUpperCase(),
            )
            .join(", ");
          showToast(data.message || `Sinhronizacija uspešna za: ${successes}!`, "success");
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
        }),
      });
      if (res.ok) {
        showToast("Podešavanja uspešno sačuvana!");
        setSaveFeedback(true);
        setTimeout(() => setSaveFeedback(false), 2500);
        await fetchStatus();
      } else {
        showToast("Greška pri čuvanju podešavanja", "error");
      }
    } catch (e: unknown) {
      showToast(errorMessage(e, "Greška na serveru"), "error");
    }
  }, [binariesPaths, fetchStatus, outputDir, showToast, transcodeMode]);

  const handleSaveDeviceWvdPath = useCallback(async () => {
    try {
      const res = await apiFetch(`/api/config`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ binaries: { device_wvd: binariesPaths.device_wvd || "" } }),
      });
      if (res.ok) {
        showToast("Putanja do device.wvd je sacuvana.");
        await fetchStatus();
      } else {
        const data = await res.json().catch(() => null);
        showToast(data?.detail || "Greska pri cuvanju device.wvd putanje", "error");
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
          showToast(`Kredencijali za ${service.toUpperCase()} uspesno sacuvani!`);
          if (data.warning) {
            showToast(data.warning, "info");
          }
          await fetchStatus();
        } else {
          showToast(data.detail || "Greška pri prijavi", "error");
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
    deviceWvdInfo,
    fetchStatus,
    subscribeStatusLoaded,
    fetchTranscodeDiagnostics,
    handleImportSession,
    handleAutoSyncBrowser,
    handleSaveConfig,
    handleSaveDeviceWvdPath,
    submitLogin,
    openOutputFolder,
  };
}

export type AppConfigSlice = ReturnType<typeof useAppConfig>;
