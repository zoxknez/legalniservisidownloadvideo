import { useCallback, useRef, useState } from "react";
import { apiFetch, parseApiError } from "../../lib/api";
import { errorMessage } from "../../utils/logUtils";
import type { SmartDetectData, SmartEpisode } from "../../types/app";
import type { ShowToastFn } from "../domainTypes";

export interface UseSmartDashboardOptions {
  showToast: ShowToastFn;
}

export function useSmartDashboard({ showToast }: UseSmartDashboardOptions) {
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
  
  const [ytdlpSponsorblockMode, setYtdlpSponsorblockMode] = useState("remove");
  const [ytdlpSplitChapters, setYtdlpSplitChapters] = useState(false);
  const [ytdlpDownloadPlaylist, setYtdlpDownloadPlaylist] = useState(false);
  const [ytdlpPlaylistItems, setYtdlpPlaylistItems] = useState("");
  
  const [smartSubmitting, setSmartSubmitting] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const abortRef = useRef<AbortController | null>(null);

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
            setSmartSelectedEpisodes(data.episodes.map((ep: SmartEpisode) => ep.id));
          }
          if (data.available_resolutions && data.available_resolutions.length > 0) {
            setSmartResolution(data.available_resolutions[0]);
          } else {
            setSmartResolution("1080p");
          }
          if (data.service === "ytdlp") {
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
    [showToast],
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
          voyoBody.video_ids = smartSelectedEpisodes.map(id => Number(id));
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
          let allOk = true;
          for (const ep of selectedEps) {
            const r = await apiFetch(`/api/hrti/download`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ ref_id: ep.id, title: ep.title, workers: 16 }),
            });
            if (!r.ok) allOk = false;
          }
          if (allOk) {
            showToast(`${selectedEps.length} epizoda uspešno dodato u red!`, "success");
            setSmartUrl("");
            setSmartData(null);
            setSmartSelectedEpisodes([]);
          } else {
            showToast("Neke epizode nisu mogle biti dodate.", "error");
          }
          return;
        }
        res = await apiFetch(`/api/hrti/download`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            ref_id: smartData.target_id,
            title: smartData.title,
            workers: 16,
          }),
        });
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
            subs: smartSubs,
          }),
        });
      } else if (smartData.service === "ytdlp") {
        res = await apiFetch(`/api/ytdlp/download`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            url: smartData.target_id,
            resolution: smartResolution,
            subs: smartSubs,
            audio_only: smartAudioOnly,
            use_aria2: smartUseAria2,
            hardsub: ytdlpHardsub,
            cookies_browser: ytdlpCookiesBrowser || null,
            impersonate_browser: ytdlpImpersonate,
            proxy: ytdlpProxy || null,
            geo_bypass: ytdlpGeoBypass,
            embed_thumbnail: ytdlpEmbedThumbnail,
            embed_metadata: ytdlpEmbedMetadata,
            limit_rate: ytdlpLimitRate || null,
            sponsorblock_mode: ytdlpSponsorblockMode,
            split_chapters: ytdlpSplitChapters,
            download_playlist: ytdlpDownloadPlaylist,
            playlist_items: ytdlpPlaylistItems || null,
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
        setYtdlpSponsorblockMode("remove");
        setYtdlpSplitChapters(false);
        setYtdlpDownloadPlaylist(false);
        setYtdlpPlaylistItems("");
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
    smartSubmitting,
    handleSmartDetect,
    debouncedDetect,
    startSmartDownload,
  };
}

export type SmartDashboardSlice = ReturnType<typeof useSmartDashboard>;
