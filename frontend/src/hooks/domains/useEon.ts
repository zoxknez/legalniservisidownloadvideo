import { useCallback, useEffect, useState } from "react";
import { apiFetch, parseApiError } from "../../lib/api";
import { errorMessage } from "../../utils/logUtils";
import type { AppStatus, EonMediaItem, ServiceStatus } from "../../types/app";
import type { ShowToastFn } from "../domainTypes";

export interface UseEonOptions {
  showToast: ShowToastFn;
  activeTab: string;
  status: AppStatus | null;
  fetchStatus: () => Promise<void>;
  fetchScheduledRecordings: () => Promise<void>;
}

export function useEon({
  showToast,
  activeTab,
  status,
  fetchStatus,
  fetchScheduledRecordings,
}: UseEonOptions) {
  const [eonUsername, setEonUsername] = useState("");
  const [eonPassword, setEonPassword] = useState("");
  const [eonSerial, setEonSerial] = useState("");
  const [eonNumber, setEonNumber] = useState("");
  const [showEonPass, setShowEonPass] = useState(false);

  const [eonMode, setEonMode] = useState<"vod" | "series" | "live">("vod");
  const [eonLiveInputMode, setEonLiveInputMode] = useState<"catalog" | "url">("catalog");
  const [eonTarget, setEonTarget] = useState("");
  const [eonDuration, setEonDuration] = useState(3600);
  const [eonEpisodesRange, setEonEpisodesRange] = useState("");
  const [eonPlay, setEonPlay] = useState(false);
  const [eonPlayerPath, setEonPlayerPath] = useState("");
  const [eonChannels, setEonChannels] = useState<string[]>([]);
  const [eonSearchQuery, setEonSearchQuery] = useState("");
  const [eonSearchResults, setEonSearchResults] = useState<EonMediaItem[]>([]);
  const [eonEpgItems, setEonEpgItems] = useState<EonMediaItem[]>([]);
  const [eonSubmitting, setEonSubmitting] = useState(false);

  const eonStatus: ServiceStatus | undefined = status?.services.eon;
  const eonReady = Boolean(eonStatus?.ready);
  const eonMissing = eonStatus?.missing ?? [];
  const eonOptionalMissing = eonStatus?.optional_missing ?? [];
  const eonRootPath = eonStatus?.script_path
    ? eonStatus.script_path.replace(/[\\/]+eon_downloader\.py$/i, "")
    : "root aplikacije";
  const eonCatalogPath = useCallback(
    (name: string) => (eonRootPath === "root aplikacije" ? name : `${eonRootPath}\\${name}`),
    [eonRootPath],
  );

  useEffect(() => {
    const eon = status?.services.eon;
    if (!eon) return;
    if (!eonUsername && eon.username) setEonUsername(eon.username);
    if (!eonSerial && eon.serial) setEonSerial(eon.serial);
    if (!eonNumber && eon.number) setEonNumber(eon.number);
  }, [status, eonUsername, eonSerial, eonNumber]);

  const fetchEonChannels = useCallback(async () => {
    try {
      const res = await apiFetch(`/api/eon/channels`);
      const data = await res.json().catch(() => null);
      if (res.ok) {
        setEonChannels(Array.isArray(data) ? data : []);
      } else {
        setEonChannels([]);
        if (activeTab === "eon") {
          showToast(data?.detail || "EON engine nije spreman.", "error");
        }
      }
    } catch (e) {
      console.error(e);
    }
  }, [activeTab, showToast]);

  useEffect(() => {
    if ((activeTab === "eon" || activeTab === "iptv") && eonChannels.length === 0) {
      void fetchEonChannels();
    }
  }, [activeTab, eonChannels.length, fetchEonChannels]);

  const startEonDownload = useCallback(async () => {
    const target = eonTarget.trim();
    if (!target || eonSubmitting) return;
    setEonSubmitting(true);
    try {
      const res = await apiFetch(`/api/eon/download`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          mode: eonMode,
          target,
          duration: eonDuration,
          episodes: eonEpisodesRange.trim(),
          play: eonPlay,
          player_path: eonPlayerPath.trim(),
        }),
      });
      if (res.ok) {
        showToast("EON download zadatak uspešno poslat!");
        setEonTarget("");
      } else {
        showToast(await parseApiError(res, "Greška pri slanju zadatka"), "error");
      }
    } catch (e: unknown) {
      showToast(errorMessage(e, "Greška na serveru"), "error");
    } finally {
      setEonSubmitting(false);
    }
  }, [
    eonDuration,
    eonEpisodesRange,
    eonMode,
    eonPlay,
    eonPlayerPath,
    eonSubmitting,
    eonTarget,
    showToast,
  ]);

  const searchEonVod = useCallback(async () => {
    if (!eonSearchQuery.trim()) return;
    try {
      const res = await apiFetch(`/api/eon/search?query=${encodeURIComponent(eonSearchQuery.trim())}`);
      const data = await res.json().catch(() => null);
      if (res.ok) {
        setEonSearchResults(Array.isArray(data) ? data : []);
        if (!Array.isArray(data) || data.length === 0) {
          showToast("Nema EON VOD rezultata u konfigurisanom API/lokalnom katalogu.", "info");
        }
      } else {
        showToast(data?.detail || "EON pretraga nije uspela", "error");
      }
    } catch (e: unknown) {
      showToast(errorMessage(e, "Greška na serveru"), "error");
    }
  }, [eonSearchQuery, showToast]);

  const fetchEonEpg = useCallback(async () => {
    if (!eonTarget) return;
    try {
      const res = await apiFetch(`/api/eon/epg?channel=${encodeURIComponent(eonTarget)}`);
      const data = await res.json().catch(() => null);
      if (res.ok) {
        setEonEpgItems(Array.isArray(data) ? data : []);
        if (!Array.isArray(data) || data.length === 0) {
          showToast("Nema EPG zapisa za izabrani kanal.", "info");
        }
      } else {
        showToast(data?.detail || "EON EPG nije dostupan", "error");
      }
    } catch (e: unknown) {
      showToast(errorMessage(e, "Greška na serveru"), "error");
    }
  }, [eonTarget, showToast]);

  const initEonCatalogs = useCallback(async () => {
    try {
      const res = await apiFetch(`/api/eon/catalogs/init`, { method: "POST" });
      const data = await res.json().catch(() => null);
      if (res.ok) {
        const created = data?.created?.length ?? 0;
        showToast(
          created ? "EON katalog fajlovi su napravljeni." : "EON katalog fajlovi već postoje.",
          "success",
        );
        void fetchEonChannels();
      } else {
        showToast(data?.detail || "Greška pri kreiranju EON kataloga", "error");
      }
    } catch (e: unknown) {
      showToast(errorMessage(e, "Greška na serveru"), "error");
    }
  }, [fetchEonChannels, showToast]);

  const loginEonApi = useCallback(async () => {
    if (!eonUsername.trim() || !eonPassword || !eonSerial.trim() || !eonNumber.trim()) {
      showToast("Popunite EON nalog, lozinku, device serial i device number.", "error");
      return;
    }
    if (eonSubmitting) return;
    setEonSubmitting(true);
    try {
      const res = await apiFetch(`/api/eon/api-login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username: eonUsername.trim(),
          password: eonPassword,
          serial: eonSerial.trim(),
          number: eonNumber.trim(),
        }),
      });
      const data = await res.json().catch(() => null);
      if (res.ok) {
        showToast(
          data?.tokens_saved
            ? "EON API token je sačuvan."
            : "API login je prošao, ali token nije pronađen u odgovoru.",
          data?.tokens_saved ? "success" : "info",
        );
        await fetchStatus();
      } else {
        showToast(await parseApiError(res, "EON API login nije uspeo"), "error");
      }
    } catch (e: unknown) {
      showToast(errorMessage(e, "Greška na serveru"), "error");
    } finally {
      setEonSubmitting(false);
    }
  }, [eonNumber, eonPassword, eonSerial, eonSubmitting, eonUsername, fetchStatus, showToast]);

  const refreshEonApiToken = useCallback(async () => {
    try {
      const res = await apiFetch(`/api/eon/refresh-token`, { method: "POST" });
      const data = await res.json().catch(() => null);
      if (res.ok) {
        showToast(
          data?.tokens_saved
            ? "EON API token je osvežen."
            : "Refresh je prošao, ali token nije pronađen u odgovoru.",
          data?.tokens_saved ? "success" : "info",
        );
        await fetchStatus();
      } else {
        showToast(data?.detail || "EON token refresh nije uspeo", "error");
      }
    } catch (e: unknown) {
      showToast(errorMessage(e, "Greška na serveru"), "error");
    }
  }, [fetchStatus, showToast]);

  const scheduleEonRecording = useCallback(
    async (channelName: string, title: string, startTime: string, durationMinutes: number) => {
      try {
        const res = await apiFetch(`/api/scheduler/schedule`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            channel_name: channelName,
            title,
            start_time: startTime,
            duration: durationMinutes,
          }),
        });
        const data = await res.json();
        if (res.ok) {
          showToast(`✓ Snimanje zakazano: ${title}`, "success");
          await fetchScheduledRecordings();
        } else {
          showToast(data.detail || "Greška pri zakazivanju snimanja.", "error");
        }
      } catch (e: unknown) {
        showToast(errorMessage(e, "Greška na serveru"), "error");
      }
    },
    [fetchScheduledRecordings, showToast],
  );

  return {
    eonUsername,
    setEonUsername,
    eonPassword,
    setEonPassword,
    eonSerial,
    setEonSerial,
    eonNumber,
    setEonNumber,
    showEonPass,
    setShowEonPass,
    eonMode,
    setEonMode,
    eonLiveInputMode,
    setEonLiveInputMode,
    eonTarget,
    setEonTarget,
    eonDuration,
    setEonDuration,
    eonEpisodesRange,
    setEonEpisodesRange,
    eonPlay,
    setEonPlay,
    eonPlayerPath,
    setEonPlayerPath,
    eonChannels,
    setEonChannels,
    eonSearchQuery,
    setEonSearchQuery,
    eonSearchResults,
    setEonSearchResults,
    eonEpgItems,
    setEonEpgItems,
    eonStatus,
    eonReady,
    eonMissing,
    eonOptionalMissing,
    eonSubmitting,
    eonRootPath,
    eonCatalogPath,
    fetchEonChannels,
    fetchEonEpg,
    searchEonVod,
    startEonDownload,
    initEonCatalogs,
    loginEonApi,
    refreshEonApiToken,
    scheduleEonRecording,
  };
}

export type EonSlice = ReturnType<typeof useEon>;
