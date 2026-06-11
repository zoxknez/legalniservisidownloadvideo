import { useCallback, useRef, useState } from "react";
import { defaultSmartEpisodeIds, VOYO_HARD_BLOCK_MSG, voyoIsHardBlocked } from "../../lib/voyoDrm";
import { apiFetch, parseApiError } from "../../lib/api";
import { errorMessage } from "../../utils/logUtils";
import type { SmartDetectData, SmartEpisode } from "../../types/app";
import type { ShowToastFn } from "../domainTypes";

export interface UseSmartDashboardOptions {
  showToast: ShowToastFn;
  ignoreCatalogDrmHint?: boolean;
}

export function useSmartDashboard({ showToast, ignoreCatalogDrmHint = false }: UseSmartDashboardOptions) {
  const [smartUrl, setSmartUrl] = useState("");
  const [smartLoading, setSmartLoading] = useState(false);
  const [smartData, setSmartData] = useState<SmartDetectData | null>(null);
  const [smartSelectedEpisodes, setSmartSelectedEpisodes] = useState<(number | string)[]>([]);
  const [smartEpisodesRange, setSmartEpisodesRange] = useState("");
  const [smartResolution, setSmartResolution] = useState("1080p");
  const [smartSubs, setSmartSubs] = useState("sr,hr,mk,bs,sl");
  const [smartRtsVerbose, setSmartRtsVerbose] = useState(false);
  const [smartRtsStartEp, setSmartRtsStartEp] = useState("");
  const [smartRtsEndEp, setSmartRtsEndEp] = useState("");
  const [smartAudioOnly, setSmartAudioOnly] = useState(false);
  const [smartUseAria2, setSmartUseAria2] = useState(false);
  
  // Advanced yt-dlp options
  const [ytdlpCookiesBrowser, setYtdlpCookiesBrowser] = useState("");
  const [ytdlpImpersonate, setYtdlpImpersonate] = useState(false);
  const [ytdlpProxy, setYtdlpProxy] = useState("");
  const [ytdlpGeoBypass, setYtdlpGeoBypass] = useState(false);
  const [ytdlpEmbedThumbnail, setYtdlpEmbedThumbnail] = useState(false);
  const [ytdlpEmbedMetadata, setYtdlpEmbedMetadata] = useState(false);
  const [ytdlpLimitRate, setYtdlpLimitRate] = useState("");
  const [ytdlpHardsub, setYtdlpHardsub] = useState(false);
  
  const [ytdlpSponsorblockMode, setYtdlpSponsorblockMode] = useState("disabled");
  const [ytdlpSplitChapters, setYtdlpSplitChapters] = useState(false);
  const [ytdlpDownloadPlaylist, setYtdlpDownloadPlaylist] = useState(false);
  const [ytdlpPlaylistItems, setYtdlpPlaylistItems] = useState("");
  const [ytdlpFormatSpec, setYtdlpFormatSpec] = useState("");
  const [ytdlpExtractorArgs, setYtdlpExtractorArgs] = useState("");
  const [ytdlpCookiesConfigured, setYtdlpCookiesConfigured] = useState(false);
  const [ytdlpCookiesUploading, setYtdlpCookiesUploading] = useState(false);

  const [smartSkyVcodec, setSmartSkyVcodec] = useState("H264");
  const [smartSkyQuality, setSmartSkyQuality] = useState("SDR");
  const [smartSkyAudioLang, setSmartSkyAudioLang] = useState("sr");
  const [smartHboAudio, setSmartHboAudio] = useState("all");
  const [smartSubmitting, setSmartSubmitting] = useState(false);
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
          const msg = await parseApiError(res, "Otpremanje kolačića nije uspelo.");
          showToast(msg, "error");
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

  const handleSmartDetect = useCallback(
    async (urlStr: string) => {
      const val = urlStr.trim();
      if (!val) return;
      if (abortRef.current) abortRef.current.abort();
      const controller = new AbortController();
      abortRef.current = controller;
      setSmartLoading(true);
      setSmartData(null);
      setSmartSelectedEpisodes([]);
      try {
        const res = await apiFetch(`/api/smart-detect?url=${encodeURIComponent(val)}`, { timeoutMs: 65_000, signal: controller.signal });
        if (res.ok) {
          const data = await res.json();
          setSmartData(data);
          if (data.episodes && data.episodes.length > 0) {
            if (data.service === "voyo") {
              setSmartSelectedEpisodes(defaultSmartEpisodeIds(data.episodes, ignoreCatalogDrmHint));
            } else {
              setSmartSelectedEpisodes(data.episodes.map((ep: SmartEpisode) => ep.id));
            }
          }
          if (data.available_resolutions && data.available_resolutions.length > 0) {
            setSmartResolution(data.available_resolutions[0]);
          } else {
            setSmartResolution("1080p");
          }
          if (data.service === "ytdlp") {
            void refreshYtdlpCookiesStatus();
            if (data.mode === "playlist") {
              setYtdlpDownloadPlaylist(true);
            }
            const manual = data.available_subtitles || [];
            const auto = data.available_auto_subtitles || [];
            const priority = ["sr", "hr", "bs", "en"];
            const matchedManual = manual.filter((l: string) => priority.includes(l.toLowerCase()));
            const matchedAuto = auto.filter((l: string) => priority.includes(l.toLowerCase()));
            if (matchedManual.length > 0) {
              setSmartSubs(matchedManual.join(","));
            } else if (matchedAuto.length > 0) {
              setSmartSubs(matchedAuto.join(","));
            } else if (manual.length > 0) {
              setSmartSubs(manual.slice(0, 2).join(","));
            } else {
              setSmartSubs("");
            }
          } else {
            setSmartSubs("sr,hr,mk,bs,sl");
          }
          if (data.service === "skyshowtime") {
            setSmartSkyVcodec("H264");
            setSmartSkyQuality("SDR");
            setSmartSkyAudioLang("sr");
          }
          if (data.service === "hbomax") {
            setSmartSubs("all");
            setSmartHboAudio("all");
          }
          showToast("Link uspešno prepoznat i analiziran!", "success");
        } else {
          const msg = await parseApiError(res, "URL nije prepoznat.");
          showToast(msg, "error");
        }
      } catch (e) {
        if (controller.signal.aborted) return;
        showToast(errorMessage(e, "Greška na serveru"), "error");
      } finally {
        if (!controller.signal.aborted) setSmartLoading(false);
      }
    },
    [ignoreCatalogDrmHint, refreshYtdlpCookiesStatus, showToast],
  );

  const debouncedDetect = useCallback(
    (urlStr: string) => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
      debounceRef.current = setTimeout(() => {
        handleSmartDetect(urlStr);
      }, 600);
    },
    [handleSmartDetect],
  );

  const startSmartDownload = useCallback(async () => {
    if (!smartData || smartSubmitting) return;

    if (smartData.service === "voyo" && smartData.mode === "video" && voyoIsHardBlocked(smartData)) {
      showToast(smartData.stream_reason || VOYO_HARD_BLOCK_MSG, "error");
      return;
    }

    setSmartSubmitting(true);
    try {
      showToast("Pokretanje pametnog preuzimanja...", "info");
      let res: Response;

      let epRange = smartEpisodesRange;
      if (!epRange && smartSelectedEpisodes.length > 0 && smartData.episodes) {
        const indices = smartData.episodes
          .map((ep: SmartEpisode, idx: number) =>
            smartSelectedEpisodes.includes(ep.id) ? idx + 1 : -1,
          )
          .filter((i: number) => i !== -1);
        if (indices.length > 0 && indices.length < smartData.episodes.length) {
          epRange = indices.join(",");
        }
      }

      if (smartData.service === "voyo") {
        const voyoBody: Record<string, unknown> = {
          target: smartData.target_id,
          mode: smartData.mode,
          resolution: smartResolution,
        };
        if (smartData.mode === "series" && smartData.episodes && smartSelectedEpisodes.length > 0) {
          const blocked = smartData.episodes.filter(
            (ep: SmartEpisode) => voyoIsHardBlocked(ep) && smartSelectedEpisodes.includes(ep.id),
          );
          if (blocked.length > 0) {
            showToast(VOYO_HARD_BLOCK_MSG, "error");
            return;
          }
          voyoBody.video_ids = smartSelectedEpisodes.map((id) => Number(id));
          voyoBody.series_title = smartData.title;
        } else if (epRange) {
          voyoBody.episodes = epRange;
        }
        res = await apiFetch(`/api/voyo/download`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(voyoBody),
        });
      } else if (smartData.service === "hrti") {
        if (smartData.episodes && smartSelectedEpisodes.length > 0) {
          const selectedEps = smartData.episodes.filter((ep: SmartEpisode) =>
            smartSelectedEpisodes.includes(ep.id),
          );
          res = await apiFetch(`/api/hrti/download`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              items: selectedEps.map((ep: SmartEpisode) => ({
                ref_id: String(ep.id),
                title: ep.title || String(ep.id),
              })),
              workers: 16,
            }),
          });
        } else {
          res = await apiFetch(`/api/hrti/download`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              ref_id: smartData.target_id,
              title: smartData.title,
              workers: 16,
            }),
          });
        }
      } else if (smartData.service === "eon") {
        res = await apiFetch(`/api/eon/download`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            mode: smartData.mode,
            target: smartData.target_id,
            episodes: epRange,
          }),
        });
      } else if (smartData.service === "rts" || smartData.service === "rtsplaneta") {
        const start = smartRtsStartEp ? parseInt(smartRtsStartEp, 10) : undefined;
        const end = smartRtsEndEp ? parseInt(smartRtsEndEp, 10) : undefined;
        res = await apiFetch(`/api/rts/download`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            target_url: smartUrl.trim(),
            start_ep: Number.isNaN(start) ? undefined : start,
            end_ep: Number.isNaN(end) ? undefined : end,
            verbose: smartRtsVerbose,
          }),
        });
      } else if (smartData.service === "hbomax") {
        res = await apiFetch(`/api/hbo/download`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            video_id: smartData.target_id,
            subs: smartSubs.trim() || "all",
            audio: smartHboAudio,
          }),
        });
      } else if (smartData.service === "skyshowtime") {
        const skyBody: Record<string, unknown> = {
          url: smartData.target_id,
          vcodec: smartSkyVcodec,
          quality: smartSkyQuality,
          audio_lang: smartSkyAudioLang || undefined,
        };
        if (smartData.mode === "series" && smartData.episodes && smartSelectedEpisodes.length > 0) {
          skyBody.episode_refs = smartSelectedEpisodes.map(String);
        }
        res = await apiFetch(`/api/skyshowtime/download`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(skyBody),
        });
      } else if (smartData.service === "ytdlp") {
        let downloadPlaylist = ytdlpDownloadPlaylist;
        let playlistItems = ytdlpPlaylistItems || null;
        if (smartData.mode === "playlist" && smartData.episodes?.length) {
          downloadPlaylist = true;
          if (
            smartSelectedEpisodes.length > 0 &&
            smartSelectedEpisodes.length < smartData.episodes.length
          ) {
            const nums = smartData.episodes
              .map((ep: SmartEpisode, idx: number) =>
                smartSelectedEpisodes.includes(ep.id) ? String(ep.episode ?? idx + 1) : null,
              )
              .filter((n: string | null): n is string => n != null);
            playlistItems = nums.join(",");
          }
        }
        res = await apiFetch(`/api/ytdlp/download`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            url: smartData.target_id,
            video_title: smartData.title || null,
            resolution: smartResolution,
            subs: smartSubs,
            audio_only: smartAudioOnly,
            use_aria2: smartUseAria2,
            hardsub: ytdlpHardsub,
            cookies_browser: ytdlpCookiesConfigured ? null : (ytdlpCookiesBrowser || null),
            impersonate_browser: ytdlpImpersonate,
            proxy: ytdlpProxy || null,
            geo_bypass: ytdlpGeoBypass,
            embed_thumbnail: ytdlpEmbedThumbnail,
            embed_metadata: ytdlpEmbedMetadata,
            limit_rate: ytdlpLimitRate || null,
            format_spec: ytdlpFormatSpec || null,
            extractor_args: ytdlpExtractorArgs || null,
            sponsorblock_mode: ytdlpSponsorblockMode,
            split_chapters: ytdlpSplitChapters,
            download_playlist: downloadPlaylist,
            playlist_items: playlistItems,
          }),
        });
      } else {
        showToast("Nepoznat servis za pametno preuzimanje.", "error");
        return;
      }

      if (res.ok) {
        showToast("Preuzimanje uspešno dodato u red!", "success");
        setSmartUrl("");
        setSmartData(null);
        setSmartSelectedEpisodes([]);
        setSmartAudioOnly(false);
        setSmartUseAria2(false);
        setYtdlpHardsub(false);
        setYtdlpCookiesBrowser("");
        setYtdlpImpersonate(false);
        setYtdlpProxy("");
        setYtdlpGeoBypass(false);
        setYtdlpEmbedThumbnail(false);
        setYtdlpEmbedMetadata(false);
        setYtdlpLimitRate("");
        setYtdlpSponsorblockMode("disabled");
        setYtdlpSplitChapters(false);
        setYtdlpDownloadPlaylist(false);
        setYtdlpPlaylistItems("");
        setYtdlpFormatSpec("");
        setYtdlpExtractorArgs("");
      } else {
        const msg = await parseApiError(res, "Greška pri pokretanju preuzimanja.");
        showToast(msg, "error");
      }
    } catch (e) {
      showToast(errorMessage(e, "Greška na serveru"), "error");
    } finally {
      setSmartSubmitting(false);
    }
  }, [
    showToast,
    smartAudioOnly,
    smartData,
    smartEpisodesRange,
    smartSubmitting,
    smartResolution,
    smartRtsVerbose,
    smartRtsStartEp,
    smartRtsEndEp,
    smartSelectedEpisodes,
    smartSubs,
    smartUrl,
    smartUseAria2,
    ytdlpHardsub,
    ytdlpCookiesBrowser,
    ytdlpImpersonate,
    ytdlpProxy,
    ytdlpGeoBypass,
    ytdlpEmbedThumbnail,
    ytdlpEmbedMetadata,
    ytdlpLimitRate,
    ytdlpSponsorblockMode,
    ytdlpSplitChapters,
    ytdlpDownloadPlaylist,
    ytdlpPlaylistItems,
    ytdlpFormatSpec,
    ytdlpExtractorArgs,
    ytdlpCookiesConfigured,
    smartSkyVcodec,
    smartSkyQuality,
    smartSkyAudioLang,
    smartHboAudio,
  ]);

  return {
    smartUrl,
    setSmartUrl,
    smartLoading,
    setSmartLoading,
    smartData,
    setSmartData,
    smartSelectedEpisodes,
    setSmartSelectedEpisodes,
    smartEpisodesRange,
    setSmartEpisodesRange,
    smartResolution,
    setSmartResolution,
    smartSubs,
    setSmartSubs,
    smartRtsVerbose,
    setSmartRtsVerbose,
    smartRtsStartEp,
    setSmartRtsStartEp,
    smartRtsEndEp,
    setSmartRtsEndEp,
    smartAudioOnly,
    setSmartAudioOnly,
    smartUseAria2,
    setSmartUseAria2,
    ytdlpHardsub,
    setYtdlpHardsub,
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
    smartSubmitting,
    smartSkyVcodec,
    setSmartSkyVcodec,
    smartSkyQuality,
    setSmartSkyQuality,
    smartSkyAudioLang,
    setSmartSkyAudioLang,
    smartHboAudio,
    setSmartHboAudio,
    handleSmartDetect,
    debouncedDetect,
    startSmartDownload,
  };
}

export type SmartDashboardSlice = ReturnType<typeof useSmartDashboard>;
