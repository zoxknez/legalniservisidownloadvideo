import { useCallback, useState } from "react";
import { apiFetch, parseApiError } from "../../lib/api";
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
  const [voyoVariant, setVoyoVariant] = useState("rs");

  const [voyoMode, setVoyoMode] = useState<"video" | "series">("video");
  const [voyoTarget, setVoyoTarget] = useState("");
  const [voyoRes, setVoyoRes] = useState("1080p");
  const [voyoSeriesData, setVoyoSeriesData] = useState<VoyoSeriesInfo | null>(null);
  const [voyoSearching, setVoyoSearching] = useState(false);
  const [selectedVoyoEpisodes, setSelectedVoyoEpisodes] = useState<number[]>([]);
  const [voyoEpisodesRange, setVoyoEpisodesRange] = useState("");
  const [voyoSubmitting, setVoyoSubmitting] = useState(false);

  const searchVoyoSeries = useCallback(async () => {
    if (!voyoTarget.trim()) return;
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
        setSelectedVoyoEpisodes(data.episodes?.map((e: SmartEpisode) => e.id) ?? []);
      } else {
        const msg = data.detail || "Neuspešno učitavanje serije";
        showToast(msg, "error");
      }
    } catch (e: unknown) {
      showToast(errorMessage(e, "Greška pri pretrazi"), "error");
    } finally {
      setVoyoSearching(false);
    }
  }, [showToast, voyoTarget]);

  const startVoyoDownload = useCallback(async () => {
    if (voyoSubmitting || !voyoTarget.trim()) return;
    setVoyoSubmitting(true);
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
            target: voyoTarget.trim(),
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
          const msg = await parseApiError(res, "Greška pri slanju zahteva");
          showToast(msg, "error");
        }
      } else {
        const res = await apiFetch(`/api/voyo/download`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            target: voyoTarget.trim(),
            mode: voyoMode,
            resolution: voyoRes,
          }),
        });
        if (res.ok) {
          showToast("Preuzimanje dodato u red!");
          setVoyoTarget("");
          setVoyoSeriesData(null);
        } else {
          const msg = await parseApiError(res, "Greška pri slanju zahteva");
          showToast(msg, "error");
        }
      }
    } catch (e: unknown) {
      showToast(errorMessage(e, "Greška na serveru"), "error");
    } finally {
      setVoyoSubmitting(false);
    }
  }, [
    showToast,
    voyoMode,
    voyoRes,
    voyoSeriesData,
    voyoSubmitting,
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
    voyoVariant,
    setVoyoVariant,
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
    voyoSubmitting,
    searchVoyoSeries,
    startVoyoDownload,
  };
}

export type VoyoSlice = ReturnType<typeof useVoyo>;
