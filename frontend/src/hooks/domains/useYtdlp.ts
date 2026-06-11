import { useCallback, useEffect, useRef, useState } from "react";
import { apiFetch, parseApiError } from "../../lib/api";
import { errorMessage } from "../../utils/logUtils";
import type { SmartDetectData, SmartEpisode } from "../../types/app";
import type { ShowToastFn } from "../domainTypes";
import { applyYtdlpDetectDefaults, buildYtdlpDownloadBody } from "./ytdlpShared";

export interface UseYtdlpOptions {
  showToast: ShowToastFn;
  activeTab?: string;
}

export function useYtdlp({ showToast, activeTab }: UseYtdlpOptions) {
  const [ytdlpUrl, setYtdlpUrl] = useState("");
  const [ytdlpLoading, setYtdlpLoading] = useState(false);
  const [ytdlpData, setYtdlpData] = useState<SmartDetectData | null>(null);
  const [ytdlpSelectedEpisodes, setYtdlpSelectedEpisodes] = useState<(number | string)[]>([]);
  const [ytdlpResolution, setYtdlpResolution] = useState("1080p");
  const [ytdlpSubs, setYtdlpSubs] = useState("");
  const [ytdlpAudioOnly, setYtdlpAudioOnly] = useState(false);
  const [ytdlpUseAria2, setYtdlpUseAria2] = useState(false);
  const [ytdlpCookiesBrowser, setYtdlpCookiesBrowser] = useState("");
  const [ytdlpImpersonate, setYtdlpImpersonate] = useState(false);
  const [ytdlpProxy, setYtdlpProxy] = useState("");
  const [ytdlpGeoBypass, setYtdlpGeoBypass] = useState(false);
  const [ytdlpEmbedThumbnail, setYtdlpEmbedThumbnail] = useState(false);
  const [ytdlpEmbedMetadata, setYtdlpEmbedMetadata] = useState(false);
  const [ytdlpLimitRate, setYtdlpLimitRate] = useState("");
  const [ytdlpHardsub, setYtdlpHardsub] = useState(false);
  const [ytdlpSponsorblockMode, setYtdlpSponsorblockMode] = useState("remove");
  const [ytdlpSplitChapters, setYtdlpSplitChapters] = useState(false);
  const [ytdlpDownloadPlaylist, setYtdlpDownloadPlaylist] = useState(false);
  const [ytdlpPlaylistItems, setYtdlpPlaylistItems] = useState("");
  const [ytdlpFormatSpec, setYtdlpFormatSpec] = useState("");
  const [ytdlpExtractorArgs, setYtdlpExtractorArgs] = useState("");
  const [ytdlpCookiesConfigured, setYtdlpCookiesConfigured] = useState(false);
  const [ytdlpCookiesUploading, setYtdlpCookiesUploading] = useState(false);
  const [ytdlpSubmitting, setYtdlpSubmitting] = useState(false);
  const [subsOpen, setSubsOpen] = useState(true);

  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const refreshYtdlpCookiesStatus = useCallback(async () => {
    try {
      const res = await apiFetch(`/api/ytdlp/cookies/status`);
      if (res.ok) {
        const data = await res.json();
        setYtdlpCookiesConfigured(!!data.configured);
      }
    } catch {
      setYtdlpCookiesConfigured(false);
    }
  }, []);

  useEffect(() => {
    if (activeTab === "ytdlp") {
      void refreshYtdlpCookiesStatus();
    }
  }, [activeTab, refreshYtdlpCookiesStatus]);

  const uploadYtdlpCookies = useCallback(
    async (file: File) => {
      setYtdlpCookiesUploading(true);
      try {
        const form = new FormData();
        form.append("file", file);
        const res = await apiFetch(`/api/ytdlp/cookies`, { method: "POST", body: form });
        if (res.ok) {
          setYtdlpCookiesConfigured(true);
          showToast("Fajl kolačića je sačuvan.", "success");
        } else {
          showToast(await parseApiError(res, "Otpremanje kolačića nije uspelo."), "error");
        }
      } catch (e) {
        showToast(errorMessage(e, "Greška pri otpremanju kolačića"), "error");
      } finally {
        setYtdlpCookiesUploading(false);
      }
    },
    [showToast],
  );

  const clearYtdlpCookies = useCallback(async () => {
    try {
      const res = await apiFetch(`/api/ytdlp/cookies`, { method: "DELETE" });
      if (res.ok) {
        setYtdlpCookiesConfigured(false);
        showToast("Sačuvani kolačići su uklonjeni.", "info");
      }
    } catch (e) {
      showToast(errorMessage(e, "Greška pri brisanju kolačića"), "error");
    }
  }, [showToast]);

  const resetYtdlpForm = useCallback(() => {
    setYtdlpAudioOnly(false);
    setYtdlpUseAria2(false);
    setYtdlpHardsub(false);
    setYtdlpCookiesBrowser("");
    setYtdlpImpersonate(false);
    setYtdlpProxy("");
    setYtdlpGeoBypass(false);
    setYtdlpEmbedThumbnail(false);
    setYtdlpEmbedMetadata(false);
    setYtdlpLimitRate("");
    setYtdlpSponsorblockMode("remove");
    setYtdlpSplitChapters(false);
    setYtdlpDownloadPlaylist(false);
    setYtdlpPlaylistItems("");
    setYtdlpFormatSpec("");
    setYtdlpExtractorArgs("");
    setSubsOpen(true);
  }, []);

  const analyzeYtdlpUrl = useCallback(
    async (urlStr: string) => {
      const val = urlStr.trim();
      if (!val) return;
      if (abortRef.current) abortRef.current.abort();
      const controller = new AbortController();
      abortRef.current = controller;
      setYtdlpLoading(true);
      setYtdlpData(null);
      setYtdlpSelectedEpisodes([]);
      try {
        const res = await apiFetch(
          `/api/smart-detect?url=${encodeURIComponent(val)}&force=ytdlp`,
          { timeoutMs: 65_000, signal: controller.signal },
        );
        if (res.ok) {
          const data = (await res.json()) as SmartDetectData;
          setYtdlpData(data);
          if (data.episodes?.length) {
            setYtdlpSelectedEpisodes(data.episodes.map((ep: SmartEpisode) => ep.id));
          }
          applyYtdlpDetectDefaults(data, {
            setResolution: setYtdlpResolution,
            setSubs: setYtdlpSubs,
            setDownloadPlaylist: setYtdlpDownloadPlaylist,
          });
          void refreshYtdlpCookiesStatus();
          showToast("Link analiziran — spreman za preuzimanje.", "success");
        } else {
          showToast(await parseApiError(res, "Analiza URL-a nije uspela."), "error");
        }
      } catch (e) {
        if (controller.signal.aborted) return;
        showToast(errorMessage(e, "Greška na serveru"), "error");
      } finally {
        if (!controller.signal.aborted) setYtdlpLoading(false);
      }
    },
    [refreshYtdlpCookiesStatus, showToast],
  );

  const debouncedAnalyze = useCallback(
    (urlStr: string) => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
      debounceRef.current = setTimeout(() => analyzeYtdlpUrl(urlStr), 600);
    },
    [analyzeYtdlpUrl],
  );

  const startYtdlpDownload = useCallback(async () => {
    if (!ytdlpData?.target_id || ytdlpSubmitting) return;
    setYtdlpSubmitting(true);
    try {
      showToast("Dodavanje u red preuzimanja...", "info");
      const body = buildYtdlpDownloadBody(ytdlpData, {
        resolution: ytdlpResolution,
        subs: ytdlpSubs,
        audioOnly: ytdlpAudioOnly,
        useAria2: ytdlpUseAria2,
        hardsub: ytdlpHardsub,
        cookiesBrowser: ytdlpCookiesBrowser || null,
        cookiesConfigured: ytdlpCookiesConfigured,
        impersonate: ytdlpImpersonate,
        proxy: ytdlpProxy || null,
        geoBypass: ytdlpGeoBypass,
        embedThumbnail: ytdlpEmbedThumbnail,
        embedMetadata: ytdlpEmbedMetadata,
        limitRate: ytdlpLimitRate || null,
        formatSpec: ytdlpFormatSpec || null,
        extractorArgs: ytdlpExtractorArgs || null,
        sponsorblockMode: ytdlpSponsorblockMode,
        splitChapters: ytdlpSplitChapters,
        downloadPlaylist: ytdlpDownloadPlaylist,
        playlistItems: ytdlpPlaylistItems || null,
        selectedEpisodes: ytdlpSelectedEpisodes,
      });
      const res = await apiFetch(`/api/ytdlp/download`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (res.ok) {
        showToast("Preuzimanje uspešno dodato u red!", "success");
        setYtdlpUrl("");
        setYtdlpData(null);
        setYtdlpSelectedEpisodes([]);
        resetYtdlpForm();
      } else {
        showToast(await parseApiError(res, "Greška pri pokretanju preuzimanja."), "error");
      }
    } catch (e) {
      showToast(errorMessage(e, "Greška na serveru"), "error");
    } finally {
      setYtdlpSubmitting(false);
    }
  }, [
    ytdlpAudioOnly,
    ytdlpCookiesBrowser,
    ytdlpCookiesConfigured,
    ytdlpData,
    ytdlpDownloadPlaylist,
    ytdlpEmbedMetadata,
    ytdlpEmbedThumbnail,
    ytdlpExtractorArgs,
    ytdlpFormatSpec,
    ytdlpGeoBypass,
    ytdlpHardsub,
    ytdlpImpersonate,
    ytdlpLimitRate,
    ytdlpPlaylistItems,
    ytdlpProxy,
    ytdlpResolution,
    ytdlpSelectedEpisodes,
    ytdlpSplitChapters,
    ytdlpSponsorblockMode,
    ytdlpSubmitting,
    ytdlpSubs,
    ytdlpUseAria2,
    resetYtdlpForm,
    showToast,
  ]);

  const cancelYtdlpPreview = useCallback(() => {
    setYtdlpData(null);
    setYtdlpUrl("");
    setYtdlpSelectedEpisodes([]);
    resetYtdlpForm();
  }, [resetYtdlpForm]);

  return {
    ytdlpUrl,
    setYtdlpUrl,
    ytdlpLoading,
    ytdlpData,
    ytdlpSelectedEpisodes,
    setYtdlpSelectedEpisodes,
    ytdlpResolution,
    setYtdlpResolution,
    ytdlpSubs,
    setYtdlpSubs,
    ytdlpAudioOnly,
    setYtdlpAudioOnly,
    ytdlpUseAria2,
    setYtdlpUseAria2,
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
    refreshYtdlpCookiesStatus,
    ytdlpSubmitting,
    subsOpen,
    setSubsOpen,
    analyzeYtdlpUrl,
    debouncedAnalyze,
    startYtdlpDownload,
    cancelYtdlpPreview,
  };
}

export type YtdlpSlice = ReturnType<typeof useYtdlp>;
