import { useState, useEffect, type ReactNode } from "react";
import type { AppContextValue } from "../types/app-context";
import { ComposeSliceProviders } from "./ComposeSliceProviders";
import { flattenAppStore, type AppStore } from "./appStore";
import { useDownloadWebSocket } from "../hooks/useDownloadWebSocket";
import { useVoyo } from "../hooks/domains/useVoyo";
import { useHrti } from "../hooks/domains/useHrti";
import { useEon } from "../hooks/domains/useEon";
import { useRts } from "../hooks/domains/useRts";
import { useHbo } from "../hooks/domains/useHbo";
import { useSmartDashboard } from "../hooks/domains/useSmartDashboard";
import { useSniffer } from "../hooks/domains/useSniffer";
import { useDownloadQueue } from "../hooks/domains/useDownloadQueue";
import { useAppConfig } from "../hooks/domains/useAppConfig";

export function AppProvider({ children }: { children: ReactNode }) {
  const [activeTab, setActiveTab] = useState("dashboard");
  const [toast, setToast] = useState<{ message: string; type: "success" | "error" | "info" } | null>(
    null,
  );
  const [toastKey, setToastKey] = useState(0);

  const showToast = (message: string, type: "success" | "error" | "info" = "success") => {
    setToastKey((k) => k + 1);
    setToast({ message, type });
    setTimeout(() => setToast(null), 5000);
  };

  const queue = useDownloadQueue({ showToast });
  const config = useAppConfig({ showToast });

  const voyo = useVoyo({ showToast });
  const hrti = useHrti({ showToast, activeTab });
  const eon = useEon({
    showToast,
    activeTab,
    status: config.status,
    fetchStatus: config.fetchStatus,
    fetchScheduledRecordings: queue.fetchScheduledRecordings,
  });
  const rts = useRts({ showToast });
  const hbo = useHbo({ showToast });
  const smart = useSmartDashboard({ showToast });
  const sniffer = useSniffer({
    showToast,
    applyTargets: {
      setActiveTab,
      setHboDirectMode: hbo.setHboDirectMode,
      setHboManifestUrl: hbo.setHboManifestUrl,
      setHboLicenseUrl: hbo.setHboLicenseUrl,
      setHboDirectTitle: hbo.setHboDirectTitle,
      setEonTarget: eon.setEonTarget,
    },
  });

  useEffect(() => {
    return config.subscribeStatusLoaded((data) => {
      if (data.sniffer?.auto_download !== undefined) {
        sniffer.setSnifferAutoDownload(Boolean(data.sniffer.auto_download));
      }
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps -- subscribeStatusLoaded and setSnifferAutoDownload are stable
  }, [config.subscribeStatusLoaded, sniffer.setSnifferAutoDownload]);

  useEffect(() => {
    void config.fetchStatus();
    void queue.fetchScheduledRecordings();
    void config.fetchTranscodeDiagnostics();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- initial bootstrap once on mount
  }, []);

  useDownloadWebSocket({
    selectedTaskRef: queue.selectedTaskRef,
    setConnected: queue.setConnected,
    setDownloads: queue.setDownloads,
    setSelectedTask: queue.setSelectedTask,
    setSniffedItems: sniffer.setSniffedItems,
    setLatestSniffed: sniffer.setLatestSniffed,
    setShowSnifferToast: sniffer.setShowSnifferToast,
    setSnifferReady: sniffer.setSnifferReady,
    setScheduledTasks: queue.setScheduledTasks,
    showToast,
    fetchStatus: config.fetchStatus,
  });

  const store: AppStore = {
    shell: {
      activeTab,
      setActiveTab,
      toast,
      toastKey,
      setToast,
      setToastKey,
      showToast,
    },
    queue,
    config,
    voyo,
    hrti,
    eon,
    rts,
    hbo,
    smart,
    sniffer,
  };

  flattenAppStore(store) satisfies AppContextValue;

  return <ComposeSliceProviders store={store}>{children}</ComposeSliceProviders>;
}
