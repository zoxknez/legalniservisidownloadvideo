import { useCallback, useEffect, useState } from "react";
import { apiFetch, parseApiError } from "../../lib/api";
import { errorMessage } from "../../utils/logUtils";
import type { HrtiItem } from "../../types/app";
import type { ShowToastFn } from "../domainTypes";

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

  const [hrtiCats, setHrtiCats] = useState<string[]>([]);
  const [selectedCat, setSelectedCat] = useState("");
  const [catItems, setCatItems] = useState<HrtiItem[]>([]);
  const [catPage, setCatPage] = useState(1);
  const [catTotalPages, setCatTotalPages] = useState(1);
  const [hrtiSearchQuery, setHrtiSearchQuery] = useState("");
  const [hrtiLoadingItems, setHrtiLoadingItems] = useState(false);
  const hrtiDownloadWorkers = 16;
  const [hrtiSubmitting, setHrtiSubmitting] = useState(false);
  const [selectedHrtiSeries, setSelectedHrtiSeries] = useState<{ id: string; title: string } | null>(
    null,
  );

  const fetchHrtiCategoryItems = useCallback(async (cat: string, page: number = 1) => {
    setHrtiLoadingItems(true);
    setSelectedHrtiSeries(null);
    try {
      const res = await apiFetch(`/api/hrti/category-items?category=${encodeURIComponent(cat)}&page=${page}`);
      if (res.ok) {
        const data = await res.json();
        setCatItems(data.items ?? []);
        setCatPage(data.metadata?.page ?? 1);
        setCatTotalPages(data.metadata?.total_pages ?? 1);
      } else {
        const msg = await parseApiError(res, "Greška pri učitavanju sadržaja");
        showToast(msg, "error");
      }
    } catch (e) {
      showToast(errorMessage(e, "Greška pri učitavanju sadržaja"), "error");
    } finally {
      setHrtiLoadingItems(false);
    }
  }, [showToast]);

  const fetchHrtiCategories = useCallback(async () => {
    try {
      const res = await apiFetch(`/api/hrti/categories`);
      if (res.ok) {
        const data = await res.json();
        setHrtiCats(data);
        if (data.length > 0) {
          setSelectedCat(data[0]);
          await fetchHrtiCategoryItems(data[0], 1);
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
    setSelectedHrtiSeries(null);
    try {
      const res = await apiFetch(`/api/hrti/search?query=${encodeURIComponent(q)}`);
      if (res.ok) {
        const data = await res.json();
        setCatItems(data.items ?? []);
        setCatPage(1);
        setCatTotalPages(1);
      } else {
        const msg = await parseApiError(res, "Pretraga nije uspela");
        showToast(msg, "error");
      }
    } catch (e) {
      showToast(errorMessage(e, "Greška pri pretrazi"), "error");
    } finally {
      setHrtiLoadingItems(false);
    }
  }, [hrtiSearchQuery, showToast]);

  const fetchHrtiSeriesEpisodes = useCallback(async (uuid: string, title: string) => {
    setHrtiLoadingItems(true);
    setSelectedHrtiSeries({ id: uuid, title });
    try {
      const res = await apiFetch(`/api/hrti/series/${encodeURIComponent(uuid)}`);
      if (res.ok) {
        const data = await res.json();
        setCatItems(data.items ?? []);
        setCatPage(1);
        setCatTotalPages(1);
      } else {
        const msg = await parseApiError(res, "Greška pri učitavanju epizoda");
        showToast(msg, "error");
      }
    } catch (e) {
      showToast(errorMessage(e, "Greška pri učitavanju epizoda"), "error");
    } finally {
      setHrtiLoadingItems(false);
    }
  }, [showToast]);

  const startHrtiDownload = useCallback((refId: string, itemTitle: string) => {
    setHrtiModalTitle(itemTitle);
    setHrtiModal({ refId, title: itemTitle });
  }, []);

  const confirmHrtiDownload = useCallback(async () => {
    if (!hrtiModal || hrtiSubmitting) return;
    setHrtiSubmitting(true);
    try {
      const res = await apiFetch(`/api/hrti/download`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ref_id: hrtiModal.refId.trim(),
          title: (hrtiModalTitle || hrtiModal.title).trim(),
          workers: hrtiDownloadWorkers,
        }),
      });
      if (res.ok) {
        showToast("HRTi preuzimanje pokrenuto!");
      } else {
        const msg = await parseApiError(res, "Greška pri slanju preuzimanja");
        showToast(msg, "error");
      }
    } catch (e: unknown) {
      showToast(errorMessage(e, "Greška na serveru"), "error");
    } finally {
      setHrtiSubmitting(false);
      setHrtiModal(null);
      setHrtiModalTitle("");
    }
  }, [hrtiModal, hrtiModalTitle, hrtiSubmitting, showToast]);

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
    hrtiLoadingItems,
    setHrtiLoadingItems,
    hrtiDownloadWorkers,
    hrtiSubmitting,
    selectedHrtiSeries,
    setSelectedHrtiSeries,
    fetchHrtiCategories,
    fetchHrtiCategoryItems,
    searchHrti,
    fetchHrtiSeriesEpisodes,
    startHrtiDownload,
    confirmHrtiDownload,
  };
}

export type HrtiSlice = ReturnType<typeof useHrti>;
