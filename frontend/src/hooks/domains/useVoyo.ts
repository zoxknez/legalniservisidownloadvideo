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
      const target = voyoTarget.trim();
      // Try resolve endpoint first (handles video URLs, IDs, and category IDs)
      const res = await apiFetch(
        `/api/voyo/resolve?target=${encodeURIComponent(target)}`
      );
      const data = await res.json();
      if (res.ok && data.success) {
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
      if (voyoMode === "series" && voyoSeriesData) {
        const ids = selectedVoyoEpisodes.filter((id) =>
          voyoSeriesData.episodes.some((ep) => ep.id === id)
        );
        if (ids.length === 0) {
          showToast("Morate selektovati barem jednu epizodu!", "error");
          return;
        }
        const res = await apiFetch(`/api/voyo/download`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            target: voyoTarget,
            mode: "series",
            video_ids: ids,
            resolution: voyoRes,
          }),
        });
        if (res.ok) {
          const data = await res.json();
          showToast(`${data.queued || ids.length} epizoda dodato u red!`);
          setVoyoTarget("");
          setVoyoSeriesData(null);
        } else {
          showToast("Greška pri slanju zahteva", "error");
        }
      } else {
        const res = await apiFetch(`/api/voyo/download`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            target: voyoTarget,
            mode: voyoMode,
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
      }
    } catch (e: unknown) {
      showToast(errorMessage(e, "Greška na serveru"), "error");
    }
  }, [
    showToast,
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
