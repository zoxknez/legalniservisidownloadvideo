import { useCallback, useEffect, useState } from "react";
import { apiFetch, parseApiError } from "../../lib/api";
import { errorMessage } from "../../utils/logUtils";
import type { HrtiCategory, HrtiItem, HrtiSeason } from "../../types/app";
import type { ShowToastFn } from "../domainTypes";

const UUID_RE =
  /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/i;

export function extractHrtiRefId(input: string): string | null {
  const trimmed = input.trim();
  if (!trimmed) return null;
  if (!trimmed.includes("/") && !/^https?:\/\//i.test(trimmed)) {
    return trimmed;
  }
  const m = trimmed.match(UUID_RE);
  return m ? m[0] : null;
}

export interface UseHrtiOptions {
  showToast: ShowToastFn;
  activeTab: string;
}

export function useHrti({ showToast, activeTab }: UseHrtiOptions) {
  const [hrtiEmail, setHrtiEmail] = useState("");
  const [hrtiPassword, setHrtiPassword] = useState("");
  const [showHrtiPass, setShowHrtiPass] = useState(false);

  const [hrtiModal, setHrtiModal] = useState<{ refId: string; title: string } | null>(null);
  const [hrtiModalTitle, setHrtiModalTitle] = useState("");

  const [hrtiCats, setHrtiCats] = useState<HrtiCategory[]>([]);
  const [selectedCat, setSelectedCat] = useState("");
  const [catItems, setCatItems] = useState<HrtiItem[]>([]);
  const [catPage, setCatPage] = useState(1);
  const [catTotalPages, setCatTotalPages] = useState(1);
  const [hrtiSearchQuery, setHrtiSearchQuery] = useState("");
  const [hrtiUrlInput, setHrtiUrlInput] = useState("");
  const [hrtiLoadingItems, setHrtiLoadingItems] = useState(false);
  const [hrtiLoadError, setHrtiLoadError] = useState<string | null>(null);
  const [hrtiWorkers, setHrtiWorkers] = useState(16);
  const [hrtiSubmitting, setHrtiSubmitting] = useState(false);

  const [selectedHrtiSeries, setSelectedHrtiSeries] = useState<{ id: string; title: string } | null>(
    null,
  );
  const [hrtiSeriesSeasons, setHrtiSeriesSeasons] = useState<HrtiSeason[]>([]);
  const [selectedHrtiEpisodes, setSelectedHrtiEpisodes] = useState<string[]>([]);
  const [viewMode, setViewMode] = useState<"catalog" | "series">("catalog");

  const applyListResponse = useCallback((data: Record<string, unknown>) => {
    if (data.success === false && data.error) {
      setHrtiLoadError(String(data.error));
      setCatItems([]);
      return;
    }
    setHrtiLoadError(null);
    setCatItems((data.items as HrtiItem[]) ?? []);
    setCatPage((data.metadata as { page?: number })?.page ?? 1);
    setCatTotalPages((data.metadata as { total_pages?: number })?.total_pages ?? 1);
  }, []);

  const fetchHrtiCategoryItems = useCallback(
    async (cat: string, page: number = 1) => {
      setHrtiLoadingItems(true);
      setViewMode("catalog");
      setSelectedHrtiSeries(null);
      setHrtiSeriesSeasons([]);
      setSelectedHrtiEpisodes([]);
      setHrtiLoadError(null);
      try {
        const res = await apiFetch(
          `/api/hrti/category-items?category=${encodeURIComponent(cat)}&page=${page}`,
        );
        if (res.ok) {
          const data = await res.json();
          applyListResponse(data);
        } else {
          const msg = await parseApiError(res, "Greška pri učitavanju sadržaja");
          setHrtiLoadError(msg);
          showToast(msg, "error");
        }
      } catch (e) {
        const msg = errorMessage(e, "Greška pri učitavanju sadržaja");
        setHrtiLoadError(msg);
        showToast(msg, "error");
      } finally {
        setHrtiLoadingItems(false);
      }
    },
    [applyListResponse, showToast],
  );

  const fetchHrtiCategories = useCallback(async () => {
    try {
      const res = await apiFetch(`/api/hrti/categories`);
      if (res.ok) {
        const data = (await res.json()) as HrtiCategory[];
        setHrtiCats(data);
        if (data.length > 0) {
          const first = data[0].id;
          setSelectedCat(first);
          await fetchHrtiCategoryItems(first, 1);
        }
      } else {
        const msg = await parseApiError(res, "Greška pri učitavanju kategorija");
        showToast(msg, "error");
      }
    } catch (e) {
      showToast(errorMessage(e, "Greška pri učitavanju kategorija"), "error");
    }
  }, [fetchHrtiCategoryItems, showToast]);

  const searchHrti = useCallback(async () => {
    const q = hrtiSearchQuery.trim();
    if (!q) return;
    setHrtiLoadingItems(true);
    setViewMode("catalog");
    setSelectedHrtiSeries(null);
    setHrtiSeriesSeasons([]);
      setSelectedHrtiEpisodes([]);
    setHrtiLoadError(null);
    try {
      const res = await apiFetch(`/api/hrti/search?query=${encodeURIComponent(q)}`);
      if (res.ok) {
        const data = await res.json();
        applyListResponse(data);
        setCatPage(1);
        setCatTotalPages(1);
      } else {
        const msg = await parseApiError(res, "Pretraga nije uspela");
        setHrtiLoadError(msg);
        showToast(msg, "error");
      }
    } catch (e) {
      const msg = errorMessage(e, "Greška pri pretrazi");
      setHrtiLoadError(msg);
      showToast(msg, "error");
    } finally {
      setHrtiLoadingItems(false);
    }
  }, [applyListResponse, hrtiSearchQuery, showToast]);

  const fetchHrtiSeriesEpisodes = useCallback(
    async (uuid: string, title: string) => {
      setHrtiLoadingItems(true);
      setViewMode("series");
      setSelectedHrtiSeries({ id: uuid, title });
      setHrtiLoadError(null);
      try {
        const res = await apiFetch(`/api/hrti/series/${encodeURIComponent(uuid)}`);
        if (res.ok) {
          const data = await res.json();
          if (data.success === false && data.error) {
            setHrtiLoadError(String(data.error));
            showToast(String(data.error), "error");
            return;
          }
          const eps = (data.items as HrtiItem[]) ?? [];
          setCatItems(eps);
          setHrtiSeriesSeasons((data.seasons as HrtiSeason[]) ?? []);
          setSelectedHrtiEpisodes(eps.map((e) => e.id));
          setSelectedHrtiSeries({
            id: uuid,
            title: (data.series_title as string) || title,
          });
          setCatPage(1);
          setCatTotalPages(1);
        } else {
          const msg = await parseApiError(res, "Greška pri učitavanju epizoda");
          setHrtiLoadError(msg);
          showToast(msg, "error");
        }
      } catch (e) {
        const msg = errorMessage(e, "Greška pri učitavanju epizoda");
        setHrtiLoadError(msg);
        showToast(msg, "error");
      } finally {
        setHrtiLoadingItems(false);
      }
    },
    [showToast],
  );

  const startHrtiDownload = useCallback((refId: string, itemTitle: string) => {
    setHrtiModalTitle(itemTitle);
    setHrtiModal({ refId, title: itemTitle });
  }, []);

  const resolveHrtiUrl = useCallback(async () => {
    const refId = extractHrtiRefId(hrtiUrlInput);
    if (!refId) {
      showToast("Unesite validan HRTi link ili Reference ID.", "error");
      return;
    }
    setHrtiLoadingItems(true);
    setHrtiLoadError(null);
    try {
      const res = await apiFetch(`/api/hrti/preview?ref_id=${encodeURIComponent(refId)}`);
      if (!res.ok) {
        const msg = await parseApiError(res, "Link nije prepoznat");
        setHrtiLoadError(msg);
        showToast(msg, "error");
        return;
      }
      const data = await res.json();
      if (data.mode === "series" && data.items?.length) {
        setViewMode("series");
        setCatItems(data.items);
        setHrtiSeriesSeasons(data.seasons ?? []);
        setSelectedHrtiEpisodes(data.items.map((e: HrtiItem) => e.id));
        setSelectedHrtiSeries({
          id: refId,
          title: data.series_title || refId,
        });
      } else {
        startHrtiDownload(refId, data.title || refId);
      }
    } catch (e) {
      const msg = errorMessage(e, "Greška pri analizi linka");
      setHrtiLoadError(msg);
      showToast(msg, "error");
    } finally {
      setHrtiLoadingItems(false);
    }
  }, [hrtiUrlInput, showToast, startHrtiDownload]);

  const submitHrtiDownload = useCallback(
    async (body: Record<string, unknown>) => {
      setHrtiSubmitting(true);
      try {
        const res = await apiFetch(`/api/hrti/download`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ ...body, workers: hrtiWorkers }),
        });
        if (res.ok) {
          const data = await res.json();
          const queued = data.queued as number | undefined;
          showToast(
            queued && queued > 1
              ? `HRTi: ${queued} epizoda dodato u red!`
              : "HRTi preuzimanje pokrenuto!",
          );
          return true;
        }
        const msg = await parseApiError(res, "Greška pri slanju preuzimanja");
        showToast(msg, "error");
        return false;
      } catch (e: unknown) {
        showToast(errorMessage(e, "Greška na serveru"), "error");
        return false;
      } finally {
        setHrtiSubmitting(false);
      }
    },
    [hrtiWorkers, showToast],
  );

  const confirmHrtiDownload = useCallback(async () => {
    if (!hrtiModal || hrtiSubmitting) return;
    const ok = await submitHrtiDownload({
      ref_id: hrtiModal.refId.trim(),
      title: (hrtiModalTitle || hrtiModal.title).trim(),
    });
    if (ok) {
      setHrtiModal(null);
      setHrtiModalTitle("");
    }
  }, [hrtiModal, hrtiModalTitle, hrtiSubmitting, submitHrtiDownload]);

  const confirmHrtiBatchDownload = useCallback(async () => {
    if (hrtiSubmitting || selectedHrtiEpisodes.length === 0) return;
    const items = catItems
      .filter((ep) => selectedHrtiEpisodes.includes(ep.id))
      .map((ep) => ({
        ref_id: ep.id,
        title: ep.title || ep.id,
      }));
    const ok = await submitHrtiDownload({ items });
    if (ok) {
      setSelectedHrtiEpisodes([]);
    }
  }, [catItems, hrtiSubmitting, selectedHrtiEpisodes, submitHrtiDownload]);

  const backToCatalog = useCallback(() => {
    setViewMode("catalog");
    setSelectedHrtiSeries(null);
    setHrtiSeriesSeasons([]);
    setSelectedHrtiEpisodes([]);
    setHrtiLoadError(null);
    if (selectedCat) {
      void fetchHrtiCategoryItems(selectedCat, catPage);
    }
  }, [catPage, fetchHrtiCategoryItems, selectedCat]);

  useEffect(() => {
    if (activeTab === "hrti" && hrtiCats.length === 0) {
      void fetchHrtiCategories();
    }
  }, [activeTab, hrtiCats.length, fetchHrtiCategories]);

  return {
    hrtiEmail,
    setHrtiEmail,
    hrtiPassword,
    setHrtiPassword,
    showHrtiPass,
    setShowHrtiPass,
    hrtiModal,
    setHrtiModal,
    hrtiModalTitle,
    setHrtiModalTitle,
    hrtiCats,
    setHrtiCats,
    selectedCat,
    setSelectedCat,
    catItems,
    setCatItems,
    catPage,
    setCatPage,
    catTotalPages,
    setCatTotalPages,
    hrtiSearchQuery,
    setHrtiSearchQuery,
    hrtiUrlInput,
    setHrtiUrlInput,
    hrtiLoadingItems,
    setHrtiLoadingItems,
    hrtiLoadError,
    hrtiWorkers,
    setHrtiWorkers,
    hrtiSubmitting,
    selectedHrtiSeries,
    setSelectedHrtiSeries,
    hrtiSeriesSeasons,
    selectedHrtiEpisodes,
    setSelectedHrtiEpisodes,
    viewMode,
    fetchHrtiCategories,
    fetchHrtiCategoryItems,
    searchHrti,
    fetchHrtiSeriesEpisodes,
    resolveHrtiUrl,
    startHrtiDownload,
    confirmHrtiDownload,
    confirmHrtiBatchDownload,
    backToCatalog,
  };
};

export type HrtiSlice = ReturnType<typeof useHrti>;
