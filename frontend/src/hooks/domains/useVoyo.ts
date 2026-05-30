import { useCallback, useState } from "react";
import { apiFetch } from "../../lib/api";
import { errorMessage } from "../../utils/logUtils";
import type { SmartEpisode, VoyoSeriesInfo } from "../../types/app";
import type { ShowToastFn } from "../domainTypes";

export interface UseVoyoOptions {
  showToast: ShowToastFn;
}

export function useVoyo({ showToast }: UseVoyoOptions) {
  const [voyoEmail, setVoyoEmail] = useState("");
  const [voyoPassword, setVoyoPassword] = useState("");
  const [showVoyoPass, setShowVoyoPass] = useState(false);

  const [voyoMode, setVoyoMode] = useState<"video" | "series">("video");
  const [voyoTarget, setVoyoTarget] = useState("");
  const [voyoRes, setVoyoRes] = useState("1080p");
  const [voyoSeriesData, setVoyoSeriesData] = useState<VoyoSeriesInfo | null>(null);
  const [voyoSearching, setVoyoSearching] = useState(false);
  const [selectedVoyoEpisodes, setSelectedVoyoEpisodes] = useState<number[]>([]);
  const [voyoEpisodesRange, setVoyoEpisodesRange] = useState("");

  const searchVoyoSeries = useCallback(async () => {
    if (!voyoTarget) return;
    setVoyoSearching(true);
    setVoyoSeriesData(null);
    try {
      let seriesId = voyoTarget.trim();
      const m = seriesId.match(/_(\d+)\.html|Series_(\d+)/i);
      if (m) seriesId = m[1] || m[2];
      const res = await apiFetch(`/api/voyo/series/${seriesId}`);
      const data = await res.json();
      if (res.ok) {
        setVoyoSeriesData(data);
        setSelectedVoyoEpisodes(data.episodes.map((e: SmartEpisode) => e.id));
      } else {
        showToast(data.detail || "Neuspešno učitavanje serije", "error");
      }
    } catch (e: unknown) {
      showToast(errorMessage(e, "Greška na serveru"), "error");
    } finally {
      setVoyoSearching(false);
    }
  }, [showToast, voyoTarget]);

  const startVoyoDownload = useCallback(async () => {
    try {
      let epRange = voyoEpisodesRange;
      if (voyoMode === "series" && voyoSeriesData && !epRange) {
        const indices = voyoSeriesData.episodes
          .map((ep, idx) => (selectedVoyoEpisodes.includes(ep.id) ? idx + 1 : -1))
          .filter((idx) => idx !== -1);
        if (indices.length === 0) {
          showToast("Morate selektovati barem jednu epizodu!", "error");
          return;
        }
        epRange = indices.join(",");
      }

      const res = await apiFetch(`/api/voyo/download`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          target: voyoTarget,
          mode: voyoMode,
          episodes: epRange,
          resolution: voyoRes,
        }),
      });
      if (res.ok) {
        showToast("Preuzimanje dodato u red!");
        setVoyoTarget("");
        setVoyoSeriesData(null);
      } else {
        showToast("Greška pri slanju zahteva", "error");
      }
    } catch (e: unknown) {
      showToast(errorMessage(e, "Greška na serveru"), "error");
    }
  }, [
    showToast,
    voyoEpisodesRange,
    voyoMode,
    voyoRes,
    voyoSeriesData,
    voyoTarget,
    selectedVoyoEpisodes,
  ]);

  return {
    voyoEmail,
    setVoyoEmail,
    voyoPassword,
    setVoyoPassword,
    showVoyoPass,
    setShowVoyoPass,
    voyoMode,
    setVoyoMode,
    voyoTarget,
    setVoyoTarget,
    voyoRes,
    setVoyoRes,
    voyoSeriesData,
    setVoyoSeriesData,
    voyoSearching,
    setVoyoSearching,
    selectedVoyoEpisodes,
    setSelectedVoyoEpisodes,
    voyoEpisodesRange,
    setVoyoEpisodesRange,
    searchVoyoSeries,
    startVoyoDownload,
  };
}

export type VoyoSlice = ReturnType<typeof useVoyo>;
