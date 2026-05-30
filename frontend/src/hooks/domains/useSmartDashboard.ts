import { useCallback, useState } from "react";
import { apiFetch } from "../../lib/api";
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
  const [smartSelectedEpisodes, setSmartSelectedEpisodes] = useState<number[]>([]);
  const [smartEpisodesRange, setSmartEpisodesRange] = useState("");
  const [smartResolution, setSmartResolution] = useState("1080p");
  const [smartSubs, setSmartSubs] = useState("sr,hr,mk,bs,sl");
  const [smartRtsVerbose, setSmartRtsVerbose] = useState(false);
  const [smartAudioOnly, setSmartAudioOnly] = useState(false);
  const [smartUseAria2, setSmartUseAria2] = useState(false);

  const handleSmartDetect = useCallback(
    async (urlStr: string) => {
      const val = urlStr.trim();
      if (!val) return;
      setSmartLoading(true);
      setSmartData(null);
      setSmartSelectedEpisodes([]);
      try {
        const res = await apiFetch(`/api/smart-detect?url=${encodeURIComponent(val)}`);
        const data = await res.json();
        if (res.ok) {
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
          showToast(data.detail || "URL nije prepoznat.", "error");
        }
      } catch (e) {
        showToast(errorMessage(e, "Greška na serveru"), "error");
      } finally {
        setSmartLoading(false);
      }
    },
    [showToast],
  );

  const startSmartDownload = useCallback(async () => {
    if (!smartData) return;
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
        res = await apiFetch(`/api/voyo/download`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            target: smartData.target_id,
            mode: smartData.mode,
            episodes: epRange,
            resolution: smartResolution,
          }),
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
        const start = smartEpisodesRange ? parseInt(smartEpisodesRange.split("-")[0], 10) : undefined;
        const end = smartEpisodesRange ? parseInt(smartEpisodesRange.split("-")[1], 10) : undefined;
        res = await apiFetch(`/api/rts/download`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            target_url: smartUrl,
            start_ep: start,
            end_ep: end,
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
          }),
        });
      } else {
        showToast("Nepoznat servis za pametno preuzimanje.", "error");
        return;
      }

      const data = await res.json();
      if (res.ok) {
        showToast("Preuzimanje uspešno dodato u red!", "success");
        setSmartUrl("");
        setSmartData(null);
        setSmartSelectedEpisodes([]);
        setSmartAudioOnly(false);
        setSmartUseAria2(false);
      } else {
        showToast(data.detail || "Greška pri pokretanju preuzimanja.", "error");
      }
    } catch (e) {
      showToast(errorMessage(e, "Greška na serveru"), "error");
    }
  }, [
    showToast,
    smartAudioOnly,
    smartData,
    smartEpisodesRange,
    smartResolution,
    smartRtsVerbose,
    smartSelectedEpisodes,
    smartSubs,
    smartUrl,
    smartUseAria2,
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
    smartAudioOnly,
    setSmartAudioOnly,
    smartUseAria2,
    setSmartUseAria2,
    handleSmartDetect,
    startSmartDownload,
  };
}

export type SmartDashboardSlice = ReturnType<typeof useSmartDashboard>;
