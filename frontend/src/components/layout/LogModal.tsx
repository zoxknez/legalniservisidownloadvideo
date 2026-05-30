import {
  Check,
  Copy,
  Maximize2,
  Minimize2,
  Terminal,
  X,
} from "lucide-react";
import { QUEUE_SERVICE_PILL_CLASS } from "../../constants/services";
import { getLogLineClass } from "../../utils/logUtils";
import { useDownloadQueuePanel } from "../../hooks/domains/useDownloadQueuePanel";

export function LogModal() {
  const {
    cancelDownloadTask,
    logCopied,
    logEndRef,
    logFullscreen,
    selectedTask,
    setLogCopied,
    setLogFullscreen,
    setSelectedTask,
    setShowLogModal,
    showLogModal,
  } = useDownloadQueuePanel();
  if (!showLogModal || !selectedTask) return null;
  return (
  <div className={`fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center ${logFullscreen ? "p-0" : "p-8"}`}
    onKeyDown={(e) => e.key === "Escape" && (setShowLogModal(false), setSelectedTask(null), setLogFullscreen(false))}
    tabIndex={-1}
  >
    <div className={`glass-panel border border-glass flex flex-col justify-between overflow-hidden shadow-2xl animate-slide ${logFullscreen ? "log-modal-fullscreen" : "w-full max-w-4xl h-[600px] rounded-xl"}`}>
      
      {/* Modal Header */}
      <div className="p-5 border-b border-glass flex justify-between items-center bg-black/20">
        <div style={{flex:1, minWidth:0}}>
          <div className="flex items-center gap-2">
            <Terminal className="w-5 h-5 text-indigo-400" />
            <h3 className="font-extrabold text-base text-white">Konzola Logova</h3>
            <span className={`queue-service-pill ${QUEUE_SERVICE_PILL_CLASS[selectedTask.service] || "queue-pill-unknown"}`}>
              {selectedTask.service}
            </span>
          </div>
          <p className="text-[10px] text-text-muted mt-1 truncate max-w-lg font-mono">{selectedTask.title}</p>
        </div>
        
        <div className="flex items-center gap-2">
          {/* Fullscreen toggle button */}
          <button
            className="log-copy-btn"
            onClick={() => setLogFullscreen((f: boolean) => !f)}
          >
            {logFullscreen ? <Minimize2 style={{width:12,height:12}} /> : <Maximize2 style={{width:12,height:12}} />}
            {logFullscreen ? "Smanji" : "Proširi"}
          </button>

          {/* Copy logs button */}
          <button
            className={`log-copy-btn ${logCopied ? "copied" : ""}`}
            onClick={() => {
              const text = selectedTask.logs.join("\n");
              navigator.clipboard.writeText(text).then(() => {
                setLogCopied(true);
                setTimeout(() => setLogCopied(false), 2000);
              });
            }}
          >
            {logCopied ? <Check style={{width:12,height:12}} /> : <Copy style={{width:12,height:12}} />}
            {logCopied ? "Kopirano!" : "Kopiraj"}
          </button>
          <button
            onClick={() => { setShowLogModal(false); setSelectedTask(null); setLogFullscreen(false); }}
            className="p-2 rounded-lg hover:bg-white/[0.05] text-text-secondary hover:text-white transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>
      </div>

      {/* Log Area with color-coded lines */}
      <div className="flex-1 p-6 overflow-y-auto bg-[#07080c] font-mono text-xs leading-relaxed flex flex-col gap-1 border-b border-glass">
        {selectedTask.logs.length === 0 ? (
          <div className="flex items-center justify-center h-full text-text-muted font-sans font-semibold">
            Čekanje na ispis konzole...
          </div>
        ) : (
          selectedTask.logs.map((line: string, idx: number) => (
            <div key={idx} className={`whitespace-pre-wrap select-text ${getLogLineClass(line)}`}>
              {line}
            </div>
          ))
        )}
        <div ref={logEndRef}></div>
      </div>

      {/* Modal Footer */}
      <div className="p-4 bg-black/20 flex justify-between items-center">
        <span className="text-[10px] font-bold text-text-secondary uppercase tracking-wider">
          Status: <span className="text-white font-extrabold">{selectedTask.status}</span>
          {selectedTask.status === "downloading" && (
            <span className="ml-3 text-indigo-400">{selectedTask.progress.toFixed(1)}% — {selectedTask.speed}</span>
          )}
        </span>
        
        {selectedTask.status === "downloading" ? (
          <button
            onClick={() => cancelDownloadTask(selectedTask.id)}
            className="btn btn-danger text-xs py-2 px-4"
          >
            <X className="w-3.5 h-3.5" />
            Otkaži Preuzimanje
          </button>
        ) : (
          <button
            onClick={() => { setShowLogModal(false); setSelectedTask(null); setLogFullscreen(false); }}
            className="btn btn-secondary text-xs py-2 px-4"
          >
            Zatvori Konzolu
          </button>
        )}
      </div>

    </div>
  </div>
  );
}
