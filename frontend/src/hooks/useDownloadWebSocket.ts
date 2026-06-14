import { useEffect, useRef, type Dispatch, type RefObject, type SetStateAction } from "react";
import { apiFetch, buildWebSocketUrl, getStoredApiKey } from "../lib/api";
import type {
  DownloadTask,
  ScheduledTask,
  SnifferCapture,
  SniffedItemEntry,
  SnifferReadyEntry,
  ToastType,
} from "../types/app";

type ShowToastFn = (message: string, type?: ToastType) => void;

interface UseDownloadWebSocketOptions {
  selectedTaskRef: RefObject<DownloadTask | null>;
  setConnected: Dispatch<SetStateAction<boolean>>;
  setDownloads: Dispatch<SetStateAction<DownloadTask[]>>;
  setSelectedTask: Dispatch<SetStateAction<DownloadTask | null>>;
  setSniffedItems: Dispatch<SetStateAction<Record<string, SniffedItemEntry>>>;
  setLatestSniffed: Dispatch<SetStateAction<SnifferCapture | null>>;
  setShowSnifferToast: Dispatch<SetStateAction<boolean>>;
  setSnifferReady: Dispatch<SetStateAction<Record<string, SnifferReadyEntry>>>;
  setScheduledTasks: Dispatch<SetStateAction<ScheduledTask[]>>;
  showToast: ShowToastFn;
  fetchStatus: () => Promise<void>;
}

const MAX_RECONNECT_DELAY = 30_000;
const HEARTBEAT_INTERVAL = 30_000;

export function useDownloadWebSocket({
  selectedTaskRef,
  setConnected,
  setDownloads,
  setSelectedTask,
  setSniffedItems,
  setLatestSniffed,
  setShowSnifferToast,
  setSnifferReady,
  setScheduledTasks,
  showToast,
  fetchStatus,
}: UseDownloadWebSocketOptions): void {
  const showToastRef = useRef(showToast);
  const fetchStatusRef = useRef(fetchStatus);
  const prevQueueRef = useRef<DownloadTask[]>([]);

  useEffect(() => {
    showToastRef.current = showToast;
    fetchStatusRef.current = fetchStatus;
  });

  useEffect(() => {
    let ws: WebSocket | undefined;
    let reconnectTimer: ReturnType<typeof setTimeout> | undefined;
    let heartbeatTimer: ReturnType<typeof setInterval> | undefined;
    let attempt = 0;
    let disposed = false;

    const clearHeartbeat = () => {
      if (heartbeatTimer) {
        clearInterval(heartbeatTimer);
        heartbeatTimer = undefined;
      }
    };

    const syncStateOnReconnect = async () => {
      try {
        const res = await apiFetch("/api/queue", { timeoutMs: 5000 });
        if (res.ok) {
          const body = (await res.json()) as DownloadTask[] | { items?: DownloadTask[] };
          const queue = Array.isArray(body) ? body : (body.items ?? []);
          setDownloads(queue);
          prevQueueRef.current = queue;
        }
      } catch {
        /* best effort */
      }
    };

    const setupSocket = (ticket: string) => {
      if (disposed) return;
      ws = new WebSocket(buildWebSocketUrl(ticket));

      ws.onopen = () => {
        const wasReconnect = attempt > 0;
        setConnected(true);
        attempt = 0;

        clearHeartbeat();
        heartbeatTimer = setInterval(() => {
          if (ws?.readyState === WebSocket.OPEN) {
            ws.send("ping");
          }
        }, HEARTBEAT_INTERVAL);

        if (wasReconnect) void syncStateOnReconnect();
      };

      ws.onmessage = (event) => {
        if (event.data === "pong") return;

        let payload: { type: string; data?: unknown };
        try {
          payload = JSON.parse(event.data as string);
        } catch {
          console.warn("Malformed WS message:", event.data);
          return;
        }

        if (payload.type === "queue_update") {
          const queue = payload.data as DownloadTask[];
          setDownloads(queue);
          const current = selectedTaskRef.current;
          if (current) {
            const updated = queue.find((d) => d.id === current.id);
            if (updated) setSelectedTask(updated);
          }

          // Trigger browser notification on completed/failed downloads
          const notificationsEnabled = localStorage.getItem("notifications_enabled") === "true";
          if (notificationsEnabled && "Notification" in window && Notification.permission === "granted") {
            for (const task of queue) {
              const prev = prevQueueRef.current.find((t) => t.id === task.id);
              if (prev && prev.status !== task.status) {
                if (task.status === "finished") {
                  new Notification("Preuzimanje završeno", {
                    body: `Uspešno preuzet fajl:\n${task.title}`,
                  });
                } else if (task.status === "failed") {
                  new Notification("Preuzimanje neuspešno", {
                    body: `Greška pri preuzimanju:\n${task.title}`,
                  });
                }
              }
            }
          }
          prevQueueRef.current = queue;

        } else if (payload.type === "sniffer_update") {
          const { service, type, url, headers, title } = payload.data as SnifferCapture;
          setSniffedItems((prev) => {
            const current = prev[service] || {};
            const updated = { ...current };
            if (type === "manifest") {
              updated.manifestUrl = url;
              if (title) updated.title = title;
            } else if (type === "license") {
              updated.licenseUrl = url;
              if (headers) updated.headers = headers;
            }
            return { ...prev, [service]: updated };
          });
          setLatestSniffed({ service, type, url, headers, title });
          setShowSnifferToast(true);
        } else if (payload.type === "sniffer_ready") {
          const { service, capture } = (payload.data || {}) as {
            service?: string;
            capture?: SnifferReadyEntry & {
              manifest_url?: string;
              license_url?: string;
              headers?: Record<string, string>;
            };
          };
          if (service && capture) {
            setSnifferReady((prev) => ({ ...prev, [service]: capture }));
            setSniffedItems((prev) => ({
              ...prev,
              [service]: {
                manifestUrl: capture.manifest_url || prev[service]?.manifestUrl,
                licenseUrl: capture.license_url || prev[service]?.licenseUrl,
                headers: capture.headers || prev[service]?.headers,
                title: capture.title || prev[service]?.title,
              },
            }));
            setLatestSniffed({
              service,
              type: "ready",
              url: capture.manifest_url || "",
              headers: capture.headers,
              title: capture.title,
            });
            setShowSnifferToast(true);
          }
        } else if (payload.type === "sniffer_download_queued") {
          const { title, auto } = (payload.data || {}) as { title?: string; auto?: boolean };
          showToastRef.current(
            auto ? `⚡ Auto-preuzimanje: ${title}` : `Preuzimanje u redu: ${title}`,
            "success",
          );
          setShowSnifferToast(false);
        } else if (payload.type === "transcode_update") {
          const { title, status, detail } = (payload.data || {}) as {
            title?: string;
            status?: string;
            detail?: string;
          };
          if (status === "started") {
            showToastRef.current(`🎬 Kompresija u toku: ${title || detail}`, "info");
          } else if (status === "finished") {
            showToastRef.current(`✓ Kompresija završena: ${title}`, "success");
            const notificationsEnabled = localStorage.getItem("notifications_enabled") === "true";
            if (notificationsEnabled && "Notification" in window && Notification.permission === "granted") {
              new Notification("Kompresija završena", {
                body: `Video uspešno komprimovan:\n${title}`,
              });
            }
          } else if (status === "failed") {
            showToastRef.current(`Kompresija nije uspela: ${title}`, "error");
            const notificationsEnabled = localStorage.getItem("notifications_enabled") === "true";
            if (notificationsEnabled && "Notification" in window && Notification.permission === "granted") {
              new Notification("Kompresija neuspešna", {
                body: `Greška pri kompresiji:\n${title}`,
              });
            }
          }
        } else if (payload.type === "session_imported") {
          const { services, message } = (payload.data || {}) as {
            services?: string[];
            message?: string;
          };
          const names = Array.isArray(services) ? services.join(", ") : "";
          showToastRef.current(message || `Sesija uvezena: ${names}`, "success");
          void fetchStatusRef.current();
        } else if (payload.type === "scheduled_update") {
          setScheduledTasks(payload.data as ScheduledTask[]);
        }
      };

      ws.onerror = () => {
        console.warn("WebSocket error — will reconnect on close");
      };

      ws.onclose = () => {
        setConnected(false);
        clearHeartbeat();
        if (disposed) return;

        const delay = Math.min(1000 * 2 ** attempt, MAX_RECONNECT_DELAY);
        attempt++;
        reconnectTimer = setTimeout(connect, delay);
      };
    };

    const connect = () => {
      if (disposed) return;
      const key = getStoredApiKey();
      if (key) {
        apiFetch("/api/ws-ticket", { method: "POST", timeoutMs: 5000 })
          .then((res) => {
            if (res.ok) return res.json();
            throw new Error("Failed to fetch WS ticket");
          })
          .then((data: any) => {
            if (disposed) return;
            const ticket = data.ticket || "";
            setupSocket(ticket);
          })
          .catch((err) => {
            console.warn("WebSocket ticket fetch failed:", err);
            if (!disposed) setupSocket("");
          });
      } else {
        setupSocket("");
      }
    };

    connect();
    return () => {
      disposed = true;
      clearHeartbeat();
      if (reconnectTimer) clearTimeout(reconnectTimer);
      ws?.close();
    };
  }, [
    selectedTaskRef,
    setConnected,
    setDownloads,
    setLatestSniffed,
    setScheduledTasks,
    setSelectedTask,
    setShowSnifferToast,
    setSniffedItems,
    setSnifferReady,
  ]);
}
