import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { apiFetch } from "../../lib/api";
import type { DownloadTask, ScheduledTask } from "../../types/app";
import type { ShowToastFn } from "../domainTypes";

export interface UseDownloadQueueOptions {
  showToast: ShowToastFn;
}

export function useDownloadQueue({ showToast }: UseDownloadQueueOptions) {
  const [downloads, setDownloads] = useState<DownloadTask[]>([]);
  const [connected, setConnected] = useState(false);
  const [scheduledTasks, setScheduledTasks] = useState<ScheduledTask[]>([]);
  const [confirmClear, setConfirmClear] = useState(false);

  const [showLogModal, setShowLogModal] = useState(false);
  const [selectedTask, setSelectedTask] = useState<DownloadTask | null>(null);
  const selectedTaskRef = useRef<DownloadTask | null>(null);
  const logEndRef = useRef<HTMLDivElement>(null);
  const [logCopied, setLogCopied] = useState(false);
  const [logFullscreen, setLogFullscreen] = useState(false);

  useEffect(() => {
    selectedTaskRef.current = selectedTask;
  }, [selectedTask]);

  useEffect(() => {
    if (logEndRef.current) {
      logEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [selectedTask?.logs]);

  const activeDownloadsCount = useMemo(
    () => downloads.filter((d) => d.status === "downloading" || d.status === "pending").length,
    [downloads],
  );

  const fetchScheduledRecordings = useCallback(async () => {
    try {
      const res = await apiFetch(`/api/scheduler/list`);
      if (res.ok) {
        const data = await res.json();
        setScheduledTasks(data);
      }
    } catch (e) {
      console.error("Failed to fetch scheduled recordings:", e);
    }
  }, []);

  const cancelDownloadTask = useCallback(
    async (id: string) => {
      try {
        await apiFetch(`/api/queue/cancel`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ id }),
        });
        showToast("Slanje zahteva za otkazivanje...", "info");
      } catch (e) {
        console.error(e);
      }
    },
    [showToast],
  );

  const retryDownloadTask = useCallback(
    async (id: string) => {
      try {
        const res = await apiFetch(`/api/queue/retry`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ id }),
        });
        if (res.ok) {
          showToast("Preuzimanje ponovo pokrenuto!", "success");
        } else {
          const err = await res.json().catch(() => ({}));
          showToast(err?.detail || "Nije moguće pokrenuti ponovo.", "error");
        }
      } catch {
        showToast("Greška na serveru", "error");
      }
    },
    [showToast],
  );

  const clearCompletedQueue = useCallback(async () => {
    try {
      await apiFetch(`/api/queue/clear`, { method: "POST" });
      showToast("Očišćen red preuzimanja!");
      setConfirmClear(false);
    } catch (e) {
      console.error(e);
    }
  }, [showToast]);

  return {
    downloads,
    setDownloads,
    connected,
    setConnected,
    scheduledTasks,
    setScheduledTasks,
    confirmClear,
    setConfirmClear,
    showLogModal,
    setShowLogModal,
    selectedTask,
    setSelectedTask,
    selectedTaskRef,
    logEndRef,
    logCopied,
    setLogCopied,
    logFullscreen,
    setLogFullscreen,
    activeDownloadsCount,
    fetchScheduledRecordings,
    cancelDownloadTask,
    retryDownloadTask,
    clearCompletedQueue,
  };
}

export type DownloadQueueSlice = ReturnType<typeof useDownloadQueue>;
