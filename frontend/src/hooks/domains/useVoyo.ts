import { useCallback, useEffect, useRef, useState } from "react";
import { apiFetch, parseApiError } from "../../lib/api";
import { errorMessage } from "../../utils/logUtils";
import { defaultVoyoEpisodeIds, VOYO_HARD_BLOCK_MSG, voyoIsHardBlocked } from "../../lib/voyoDrm";
import type { VoyoSeriesInfo, VoyoVideoInfo } from "../../types/app";
import type { ShowToastFn } from "../domainTypes";

export interface UseVoyoOptions {
  showToast: ShowToastFn;
  ignoreCatalogDrmHint?: boolean;
}

function parseVoyoVideoId(target: string): number | null {
  const val = target.trim();
  if (!val) return null;
  if (/^\d+$/.test(val)) return Number(val);
  const m = val.match(/_(\d+)\.html|[?&]id=(\d+)/i);
  if (m) return Number(m[1] || m[2]);
  return null;
}

export function useVoyo({ showToast, ignoreCatalogDrmHint = false }: UseVoyoOptions) {
  const [voyoEmail, setVoyoEmail] = useState("");
  const [voyoPassword, setVoyoPassword] = useState("");
  const [showVoyoPass, setShowVoyoPass] = useState(false);
  const [voyoVariant, setVoyoVariant] = useState("rs");

  const [voyoMode, setVoyoMode] = useState<"video" | "series">("video");
  const [voyoTarget, setVoyoTarget] = useState("");
  const [voyoRes, setVoyoRes] = useState("1080p");
  const [voyoSeriesData, setVoyoSeriesData] = useState<VoyoSeriesInfo | null>(null);
  const [voyoVideoPreview, setVoyoVideoPreview] = useState<VoyoVideoInfo | null>(null);
  const [voyoSearching, setVoyoSearching] = useState(false);
  const [voyoPreviewLoading, setVoyoPreviewLoading] = useState(false);
  const [selectedVoyoEpisodes, setSelectedVoyoEpisodes] = useState<number[]>([]);
  const [voyoEpisodesRange, setVoyoEpisodesRange] = useState("");
  const [voyoSubmitting, setVoyoSubmitting] = useState(false);

  const previewDebounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const searchVoyoSeries = useCallback(async () => {
    if (!voyoTarget.trim()) return;
    setVoyoSearching(true);
    setVoyoSeriesData(null);
    setVoyoVideoPreview(null);
    try {
      const target = voyoTarget.trim();
      const res = await apiFetch(`/api/voyo/resolve?target=${encodeURIComponent(target)}`);
      const data = await res.json();
      if (res.ok && data.success) {
        setVoyoSeriesData(data);
        setSelectedVoyoEpisodes(defaultVoyoEpisodeIds(data.episodes ?? [], ignoreCatalogDrmHint));
      } else {
        showToast(data.detail || "Neuspešno učitavanje serije", "error");
      }
    } catch (e: unknown) {
      showToast(errorMessage(e, "Greška pri pretrazi"), "error");
    } finally {
      setVoyoSearching(false);
    }
  }, [ignoreCatalogDrmHint, showToast, voyoTarget]);

  const fetchVoyoVideoPreview = useCallback(
    async (target: string) => {
      const vid = parseVoyoVideoId(target);
      if (!vid) {
        setVoyoVideoPreview(null);
        return;
      }
      setVoyoPreviewLoading(true);
      try {
        const res = await apiFetch(`/api/voyo/video/${vid}`);
        const data = await res.json();
        if (res.ok && data.success) {
          setVoyoVideoPreview(data);
        } else {
          setVoyoVideoPreview(null);
        }
      } catch {
        setVoyoVideoPreview(null);
      } finally {
        setVoyoPreviewLoading(false);
      }
    },
    [],
  );

  const debouncedVideoPreview = useCallback(
    (target: string) => {
      if (previewDebounceRef.current) clearTimeout(previewDebounceRef.current);
      previewDebounceRef.current = setTimeout(() => {
        if (voyoMode === "video") void fetchVoyoVideoPreview(target);
      }, 600);
    },
    [fetchVoyoVideoPreview, voyoMode],
  );

  useEffect(() => {
    if (voyoMode === "video" && voyoTarget.trim()) {
      debouncedVideoPreview(voyoTarget);
    } else {
      setVoyoVideoPreview(null);
    }
  }, [voyoMode, voyoTarget, debouncedVideoPreview]);

  const startVoyoDownload = useCallback(async () => {
    if (voyoSubmitting || !voyoTarget.trim()) return;

    if (voyoMode === "video" && voyoVideoPreview && voyoIsHardBlocked(voyoVideoPreview)) {
      showToast(voyoVideoPreview.stream_reason || VOYO_HARD_BLOCK_MSG, "error");
      return;
    }

    setVoyoSubmitting(true);
    try {
      if (voyoMode === "series" && voyoSeriesData) {
        const ids = selectedVoyoEpisodes.filter((id) => {
          const ep = voyoSeriesData.episodes.find((e) => e.id === id);
          return ep && !voyoIsHardBlocked(ep);
        });
        if (ids.length === 0) {
          showToast("Izaberite bar jednu epizodu sa dostupnim streamom.", "error");
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
            series_title: voyoSeriesData.title,
          }),
        });
        if (res.ok) {
          const data = await res.json();
          showToast(`${data.queued || ids.length} epizoda dodato u red!`, "success");
          setVoyoTarget("");
          setVoyoEpisodesRange("");
          setVoyoSeriesData(null);
          setVoyoVideoPreview(null);
        } else {
          showToast(await parseApiError(res, "Greška pri slanju zahteva"), "error");
        }
      } else {
        const res = await apiFetch(`/api/voyo/download`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            target: voyoTarget.trim(),
            mode: voyoMode,
            episodes: voyoMode === "series" ? voyoEpisodesRange.trim() : "",
            resolution: voyoRes,
          }),
        });
        if (res.ok) {
          showToast("Preuzimanje dodato u red!", "success");
          setVoyoTarget("");
          setVoyoEpisodesRange("");
          setVoyoSeriesData(null);
          setVoyoVideoPreview(null);
        } else {
          showToast(await parseApiError(res, "Greška pri slanju zahteva"), "error");
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
    voyoEpisodesRange,
    selectedVoyoEpisodes,
    voyoVideoPreview,
    ignoreCatalogDrmHint,
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
    voyoVideoPreview,
    setVoyoVideoPreview,
    voyoSearching,
    voyoPreviewLoading,
    selectedVoyoEpisodes,
    setSelectedVoyoEpisodes,
    voyoEpisodesRange,
    setVoyoEpisodesRange,
    voyoSubmitting,
    searchVoyoSeries,
    fetchVoyoVideoPreview,
    startVoyoDownload,
    ignoreCatalogDrmHint,
  };
}

export type VoyoSlice = ReturnType<typeof useVoyo>;
