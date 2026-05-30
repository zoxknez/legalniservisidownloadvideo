import {
  Inbox,
  RotateCcw,
  Terminal,
  X,
} from "lucide-react";

import { QUEUE_SERVICE_PILL_CLASS, QUEUE_CARD_BORDER_CLASS } from "../../constants/services";
import type { DownloadTask } from "../../types/app";
import { useDownloadQueuePanel } from "../../hooks/domains/useDownloadQueuePanel";

export function DownloadQueuePanel() {
  const {
    activeDownloadsCount,
    cancelDownloadTask,
    clearCompletedQueue,
    confirmClear,
    downloads,
    retryDownloadTask,
    setConfirmClear,
    setSelectedTask,
    setShowLogModal,
  } = useDownloadQueuePanel();
  return (
<aside className="w-80 glass-panel border-l border-glass p-6 flex flex-col justify-between max-h-screen overflow-y-auto">
  <div>
    <div className="flex justify-between items-center mb-6">
      <div className="flex items-center gap-2">
        <h3 className="font-extrabold text-base text-white tracking-wide uppercase">Red Preuzimanja</h3>
        {activeDownloadsCount > 0 && (
          <span className="nav-badge">{activeDownloadsCount}</span>
        )}
      </div>

      {/* F1: Confirm before clearing */}
      {downloads.length > 0 && (
        confirmClear ? (
          <div className="confirm-row">
            <span className="text-[10px] text-text-secondary font-bold">Sigurno?</span>
            <button
              onClick={clearCompletedQueue}
              className="text-[10px] text-red-400 font-extrabold hover:underline"
            >
              Da
            </button>
            <button
              onClick={() => setConfirmClear(false)}
              className="text-[10px] text-text-muted font-extrabold hover:underline"
            >
              Ne
            </button>
          </div>
        ) : (
          <button
            onClick={() => setConfirmClear(true)}
            className="text-[10px] text-indigo-400 font-extrabold hover:underline uppercase tracking-wider"
          >
            Očisti sve
          </button>
        )
      )}
    </div>

    {/* Premium empty state */}
    {downloads.length === 0 ? (
      <div className="queue-empty-state">
        <div className="queue-empty-icon">
          <Inbox style={{width:24,height:24,color:"var(--text-muted)"}} />
        </div>
        <p className="text-sm font-bold text-text-secondary">Red je prazan</p>
        <p className="text-xs text-text-muted mt-1" style={{maxWidth:180}}>Pokrenite preuzimanje iz bilo kog servisa i pojaviće se ovde.</p>
      </div>
    ) : (
      <div className="flex flex-col gap-3">
        {downloads.map((task: DownloadTask) => {
          const svcKey = task.service in QUEUE_CARD_BORDER_CLASS ? task.service : "unknown";
          const pillClass = QUEUE_SERVICE_PILL_CLASS[task.service] || "queue-pill-unknown";
          const borderClass = QUEUE_CARD_BORDER_CLASS[svcKey] || "queue-card-unknown";
          const statusColorMap = {
            pending:     "text-indigo-400",
            downloading: "text-white",
            finished:    "text-emerald-400",
            failed:      "text-red-400",
            cancelled:   "text-text-secondary"
          };
          return (
            <div key={task.id} className={`p-4 rounded-xl border border-glass bg-white/[0.01] flex flex-col gap-3 ${borderClass}`}
              style={{transition: "background 0.15s"}}>
              
              <div className="flex justify-between items-start gap-2">
                <div style={{flex:1, minWidth:0}}>
                  <div className="flex items-center gap-2 mb-1.5">
                    <span className={`queue-service-pill ${pillClass}`}>
                      {task.service}
                    </span>
                    <span className={`text-[10px] font-bold uppercase tracking-wider ${statusColorMap[task.status]}`}>
                      {task.status}
                    </span>
                  </div>
                  <h4 className="font-bold text-xs leading-snug line-clamp-2 text-white">{task.title}</h4>
                </div>

                {(task.status === "downloading" || task.status === "pending") && (
                  <button
                    onClick={() => cancelDownloadTask(task.id)}
                    className="p-1 rounded hover:bg-white/[0.05] text-text-muted hover:text-red-400 transition flex-shrink-0"
                    title="Otkaži"
                  >
                    <X className="w-4 h-4" />
                  </button>
                )}
              </div>

              {task.status === "downloading" && (
                <div className="flex flex-col gap-1.5">
                  <div className="w-full h-1.5 rounded-full bg-white/[0.04] overflow-hidden">
                    <div
                      className="h-full progress-shimmer transition-all duration-300 rounded-full"
                      style={{ width: `${task.progress}%` }}
                    ></div>
                  </div>
                  <div className="flex justify-between items-center text-[10px] text-text-secondary font-mono font-bold">
                    <span>{task.progress.toFixed(1)}%</span>
                    <span>{task.speed}</span>
                    <span>{task.eta}</span>
                  </div>
                </div>
              )}

              {task.status === "failed" && (
                <div className="text-[10px] text-text-muted font-semibold px-1">
                  ⚠ Preuzimanje nije uspelo — pokrenite ponovo iz odgovarajućeg taba.
                </div>
              )}

              <div className="flex gap-2">
                <button
                  onClick={() => {
                    setSelectedTask(task);
                    setShowLogModal(true);
                  }}
                  className="queue-logs-btn"
                  style={{ flex: 1 }}
                >
                  <Terminal style={{width:11,height:11}} />
                  Logovi
                </button>

                {(task.status === "failed" || task.status === "cancelled") && (
                  <button
                    onClick={() => retryDownloadTask(task.id)}
                    className="queue-retry-btn"
                    style={{ flex: 1 }}
                  >
                    <RotateCcw style={{width:11,height:11}} />
                    Ponovi
                  </button>
                )}
              </div>
            </div>
          );
        })}
      </div>
    )}
  </div>
</aside>

  );
}
