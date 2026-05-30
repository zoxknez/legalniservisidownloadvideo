import { useEffect, useRef, type Dispatch, type RefObject, type SetStateAction } from "react";
import { buildWebSocketUrl } from "../lib/api";
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

/** Single persistent WebSocket for queue, sniffer, transcode, and scheduler events. */
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

  useEffect(() => {
    showToastRef.current = showToast;
    fetchStatusRef.current = fetchStatus;
  });

  useEffect(() => {
    let ws: WebSocket | undefined;
    let reconnectTimer: ReturnType<typeof setTimeout> | undefined;

    const connect = () => {
      ws = new WebSocket(buildWebSocketUrl());

      ws.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data as string) as {
            type: string;
            data?: unknown;
          };

          if (payload.type === "queue_update") {
            const queue = payload.data as DownloadTask[];
            setDownloads(queue);
            const current = selectedTaskRef.current;
            if (current) {
              const updated = queue.find((d) => d.id === current.id);
              if (updated) setSelectedTask(updated);
            }
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
            } else if (status === "failed") {
              showToastRef.current(`Kompresija nije uspela: ${title}`, "error");
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
        } catch (e) {
          console.error("Failed to parse WS payload:", e);
        }
      };

      ws.onclose = () => {
        setConnected(false);
        reconnectTimer = setTimeout(connect, 3000);
      };

      ws.onopen = () => {
        setConnected(true);
      };
    };

    connect();
    return () => {
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
