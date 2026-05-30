import { useState, useEffect, useCallback, type ReactNode } from "react";
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

type BootState = "loading" | "ready" | "error";

function BootLoader({ state, error, onRetry }: { state: BootState; error: string; onRetry: () => void }) {
  if (state === "loading") {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen gap-6" style={{ background: "var(--bg-primary)" }}>
        <div className="flex flex-col gap-4 w-80">
          <div className="skeleton" style={{ height: 40, borderRadius: 12 }} />
          <div className="skeleton" style={{ height: 20, width: "60%", borderRadius: 8 }} />
          <div className="skeleton" style={{ height: 200, borderRadius: 12 }} />
          <div className="skeleton" style={{ height: 16, width: "80%", borderRadius: 8 }} />
        </div>
      </div>
    );
  }
  if (state === "error") {
    return (
      <div className="error-overlay" style={{ background: "var(--bg-primary)", minHeight: "100vh" }}>
        <svg className="error-overlay-icon" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z" />
        </svg>
        <h2 className="error-overlay-title">Server nije dostupan</h2>
        <p className="error-overlay-message">{error || "Nije moguće uspostaviti vezu sa backend serverom. Proverite da li je server pokrenut."}</p>
        <button className="error-overlay-retry" onClick={onRetry}>Ponovi povezivanje</button>
      </div>
    );
  }
  return null;
}

export function AppProvider({ children }: { children: ReactNode }) {
  const [bootState, setBootState] = useState<BootState>("loading");
  const [bootError, setBootError] = useState("");
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
      const svc = data.services;
      voyo.setVoyoEmail(svc?.voyo?.email || "");
      voyo.setVoyoPassword("");
      hrti.setHrtiEmail(svc?.hrti?.email || "");
      hrti.setHrtiPassword("");
      const rtsEmail = svc?.rtsplaneta?.email;
      if (rtsEmail && !String(rtsEmail).startsWith("(sesija")) {
        rts.setRtsEmail(rtsEmail);
      } else if (!rtsEmail) {
        rts.setRtsEmail("");
      }
      rts.setRtsPassword("");
      eon.setEonUsername(svc?.eon?.username || "");
      eon.setEonPassword("");
      eon.setEonSerial(svc?.eon?.serial || "");
      eon.setEonNumber(svc?.eon?.number || "");
      const hboMarket = svc?.hbomax?.market;
      if (hboMarket === "emea" || hboMarket === "latam" || hboMarket === "us") {
        hbo.setHboMarket(hboMarket);
      }
      hbo.refreshAuth();
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps -- stable setter refs from domain hooks
  }, [config.subscribeStatusLoaded, sniffer.setSnifferAutoDownload, hbo.setHboMarket, hbo.refreshAuth]);

  useEffect(() => {
    if (activeTab === "settings") {
      void config.fetchTranscodeDiagnostics();
    }
  }, [activeTab, config.fetchTranscodeDiagnostics]);

  const bootstrap = useCallback(async () => {
    setBootState("loading");
    setBootError("");
    try {
      await config.fetchStatus();
      setBootState("ready");
      void queue.fetchScheduledRecordings();
      void config.fetchTranscodeDiagnostics();
    } catch (e) {
      setBootState("error");
      setBootError(e instanceof Error ? e.message : "Nepoznata greška");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- stable refs
  }, []);

  useEffect(() => {
    void bootstrap();
  }, [bootstrap]);

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

  if (bootState !== "ready") {
    return <BootLoader state={bootState} error={bootError} onRetry={bootstrap} />;
  }

  return <ComposeSliceProviders store={store}>{children}</ComposeSliceProviders>;
}
