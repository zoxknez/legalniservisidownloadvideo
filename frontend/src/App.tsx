import { useState, useEffect, useRef, useLayoutEffect } from "react";
import type React from "react";
import { createPortal } from "react-dom";
import { 
  Tv, 
  Download, 
  Settings, 
  Search, 
  Terminal, 
  X, 
  CheckCircle2, 
  AlertCircle, 
  Loader2, 
  Lock, 
  FileText, 
  Play, 
  Film, 
  List, 
  Info,
  Server,
  User,
  ShieldAlert,
  Inbox,
  Radio,
  Zap,
  Globe,
  Sparkles,
  Copy,
  Check,
  Clapperboard,
  Maximize2,
  Minimize2,
  RotateCcw
} from "lucide-react";

// Interface definitions
interface BinaryStatus {
  found: boolean;
  path: string;
}

interface ServiceStatus {
  authenticated: boolean;
  ready?: boolean;
  engine_installed?: boolean;
  engine_download_supported?: boolean;
  dependency_ready?: boolean;
  engine_status?: {
    message?: string;
    download_supported?: boolean;
    cdm_ready?: boolean;
    api?: {
      configured?: boolean;
      base_url?: string;
    };
    token?: {
      configured?: boolean;
      expires_at?: string | null;
      expired?: boolean;
    };
  };
  email?: string;
  username?: string;
  nickname?: string;
  subscribed?: boolean;
  error?: string;
  serial?: string;
  number?: string;
  script_path?: string;
  missing?: string[];
  optional_missing?: string[];
}

interface AppStatus {
  binaries: Record<string, BinaryStatus>;
  output_dir: string;
  services: Record<string, ServiceStatus>;
}

interface DownloadTask {
  id: string;
  service: string;
  title: string;
  status: "pending" | "downloading" | "finished" | "failed" | "cancelled";
  progress: number;
  speed: string;
  eta: string;
  logs: string[];
}

interface HrtiItem {
  id: string;
  type: string;
  title: string;
}

interface VoyoEpisode {
  id: number;
  title: string;
  season: number;
  episode: number;
  length_mins: number;
  drm: boolean;
  has_subs: boolean;
}

interface VoyoSeriesInfo {
  title: string;
  description: string;
  episodes: VoyoEpisode[];
}

interface EonMediaItem {
  id?: string;
  title?: string;
  name?: string;
  url?: string;
  start?: string;
  end?: string;
  description?: string;
}

// V7: Log line color classifier
function getLogLineClass(line: string): string {
  const l = line.toLowerCase();
  if (l.includes("error") || l.includes("failed") || l.includes("exception") || l.includes("[download failed")) {
    return "log-line-error";
  }
  if (l.includes("warning") || l.includes("warn")) {
    return "log-line-warning";
  }
  if (l.includes("completed successfully") || l.includes("finished") || l.includes("done") || l.includes("100%")) {
    return "log-line-success";
  }
  if (l.includes("[running command]") || l.includes("info") || l.startsWith("[")) {
    return "log-line-info";
  }
  return "log-line-default";
}

function errorMessage(error: unknown, fallback: string): string {
  return error instanceof Error ? error.message : fallback;
}


// Service metadata for sidebar
const SERVICE_META = [
  { id: "dashboard", label: "Pametno Preuzimanje", icon: Zap,         colorClass: "text-amber-400",   activeBg: "bg-amber-500",  activeGlow: "rgba(251,191,36,0.3)"  },
  { id: "voyo",     label: "Voyo RS",              icon: Tv,           colorClass: "service-voyo",     activeBg: "bg-orange-600", activeGlow: "rgba(249,115,22,0.3)"  },
  { id: "hrti",     label: "HRTi Catalog",         icon: Film,         colorClass: "service-hrti",     activeBg: "bg-cyan-600",   activeGlow: "rgba(6,182,212,0.3)"   },
  { id: "eon",      label: "EON TV",               icon: Play,         colorClass: "service-eon",      activeBg: "bg-emerald-600",activeGlow: "rgba(16,185,129,0.3)"  },
  { id: "rts",      label: "RTS Planeta",          icon: Radio,        colorClass: "service-rts",      activeBg: "bg-rose-600",   activeGlow: "rgba(244,63,94,0.3)"   },
  { id: "hbo",      label: "HBO Max",              icon: Clapperboard, colorClass: "service-hbo",      activeBg: "bg-purple-600", activeGlow: "rgba(147,51,234,0.3)"  },
  { id: "settings", label: "Postavke",             icon: Settings,     colorClass: "text-text-muted",  activeBg: "bg-indigo-600", activeGlow: "rgba(99,102,241,0.3)"  },
];

// Queue service helpers
const QUEUE_SERVICE_PILL_CLASS: Record<string, string> = {
  voyo:    "queue-pill-voyo",
  hrti:    "queue-pill-hrti",
  eon:     "queue-pill-eon",
  rts:     "queue-pill-rts",
  hbomax:  "queue-pill-hbomax",
};
const QUEUE_CARD_BORDER_CLASS: Record<string, string> = {
  voyo:   "queue-card-voyo",
  hrti:   "queue-card-hrti",
  eon:    "queue-card-eon",
  rts:    "queue-card-rts",
  hbomax: "queue-card-hbomax",
};

// ── Custom Dropdown Select Component (Portal-based) ──────────────────────────
// Uses React Portal to render dropdown in document.body, escaping any
// parent backdrop-filter / overflow stacking context that would clip it.
interface CustomSelectProps {
  value: string;
  options: string[];
  onChange: (val: string) => void;
  formatLabel?: (val: string) => string;
  className?: string;
  placeholder?: string;
  searchPlaceholder?: string;
}

function CustomSelect({ value, options, onChange, formatLabel, className = "", placeholder, searchPlaceholder = "Pretraži..." }: CustomSelectProps) {
  const [open, setOpen] = useState(false);
  const [dropdownStyle, setDropdownStyle] = useState<React.CSSProperties | null>(null);
  const [filter, setFilter] = useState("");
  const triggerRef = useRef<HTMLButtonElement>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const searchInputRef = useRef<HTMLInputElement>(null);

  // Recalculate position whenever dropdown opens
  useLayoutEffect(() => {
    if (open && triggerRef.current) {
      const rect = triggerRef.current.getBoundingClientRect();
      const spaceBelow = window.innerHeight - rect.bottom;
      const filteredCount = options.filter(opt =>
        (formatLabel ? formatLabel(opt) : opt).toLowerCase().includes(filter.toLowerCase())
      ).length;
      const hasSearch = options.length > 8;
      const searchHeight = hasSearch ? 45 : 0;
      const dropdownH = Math.min(filteredCount * 40 + searchHeight + 8, 280);
      const goUp = spaceBelow < dropdownH && rect.top > dropdownH;

      setDropdownStyle({
        position: "fixed",
        left: rect.left,
        right: "auto",
        width: rect.width,
        zIndex: 9999,
        ...(goUp
          ? { bottom: window.innerHeight - rect.top + 6 }
          : { top: rect.bottom + 6 }),
      });
    } else {
      setDropdownStyle(null);
    }
  }, [open, options.length, filter]);

  // Focus search input when dropdown opens
  useEffect(() => {
    if (open && searchInputRef.current) {
      const timer = setTimeout(() => {
        searchInputRef.current?.focus();
      }, 50);
      return () => clearTimeout(timer);
    }
  }, [open]);

  // Reset filter when closed
  useEffect(() => {
    if (!open) {
      setFilter("");
    }
  }, [open]);

  // Close on outside click
  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      const t = e.target as Node;
      if (!triggerRef.current?.contains(t) && !dropdownRef.current?.contains(t)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [open]);

  // Close on scroll / resize
  useEffect(() => {
    if (!open) return;
    const close = (e: Event) => {
      if (dropdownRef.current?.contains(e.target as Node)) {
        return;
      }
      setOpen(false);
    };
    window.addEventListener("scroll", close, true);
    window.addEventListener("resize", close);
    return () => {
      window.removeEventListener("scroll", close, true);
      window.removeEventListener("resize", close);
    };
  }, [open]);

  const label = value
    ? (formatLabel ? formatLabel(value) : value)
    : (placeholder ?? "-- Izaberi --");

  const filteredOptions = options.filter(opt =>
    (formatLabel ? formatLabel(opt) : opt).toLowerCase().includes(filter.toLowerCase())
  );

  const dropdown = (open && dropdownStyle) ? createPortal(
    <div
      ref={dropdownRef}
      className="custom-select-dropdown"
      style={dropdownStyle}
    >
      {options.length > 8 && (
        <div className="custom-select-search-wrap">
          <input
            ref={searchInputRef}
            type="text"
            placeholder={searchPlaceholder}
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            className="custom-select-search-input"
            onClick={(e) => e.stopPropagation()}
          />
        </div>
      )}
      {filteredOptions.length > 0 ? (
        filteredOptions.map(opt => (
          <button
            key={opt}
            type="button"
            onClick={() => { onChange(opt); setOpen(false); }}
            className={`custom-select-option ${value === opt ? "selected" : ""}`}
          >
            {formatLabel ? formatLabel(opt) : opt}
            {value === opt && (
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" style={{marginLeft: "auto", flexShrink: 0}}>
                <polyline points="20 6 9 17 4 12" />
              </svg>
            )}
          </button>
        ))
      ) : (
        <div style={{ padding: "12px 14px", color: "var(--text-muted)", fontSize: "0.8rem", textAlign: "center" }}>
          Nema rezultata
        </div>
      )}
    </div>,
    document.body
  ) : null;

  return (
    <div className={`custom-select-wrap ${className}`}>
      <button
        ref={triggerRef}
        type="button"
        onClick={() => setOpen(o => !o)}
        className={`custom-select-trigger ${open ? "open" : ""}`}
      >
        <span className="custom-select-value">{label}</span>
        <svg className={`custom-select-chevron ${open ? "rotated" : ""}`} width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
          <polyline points="6 9 12 15 18 9" />
        </svg>
      </button>
      {dropdown}
    </div>
  );
}

interface BinaryPathCardProps {
  name: string;
  found: boolean;
  pathValue: string;
  onChange: (val: string) => void;
  showToast: (msg: string, type: "success" | "error" | "info") => void;
}

function BinaryPathCard({ name, found, pathValue, onChange, showToast }: BinaryPathCardProps) {
  const [copied, setCopied] = useState<boolean>(false);
  const display = name.toUpperCase().replace("_", ".");
  return (
    <div
      className="exec-monitor-card flex flex-col gap-3 group"
      style={{
        "--hover-border": found ? "rgba(16, 185, 129, 0.2)" : "rgba(239, 68, 68, 0.2)"
      } as any}
    >
      <div className="flex justify-between items-center">
        <div className="flex items-center gap-2">
          <span className={`exec-status-dot ${found ? "active" : "missing"}`} />
          <span className="text-sm font-extrabold text-white tracking-wide">{display}</span>
        </div>
        <button
          type="button"
          title="Kopiraj putanju"
          onClick={async () => {
            try {
              await navigator.clipboard.writeText(pathValue || "");
              setCopied(true);
              setTimeout(() => setCopied(false), 2000);
              showToast(`${display} putanja kopirana!`, "success");
            } catch {}
          }}
          className="exec-copy-btn text-text-muted hover:text-white p-1 rounded transition-colors"
        >
          {copied ? (
            <svg className="w-3.5 h-3.5 text-emerald-400" fill="none" stroke="currentColor" strokeWidth="2.5" viewBox="0 0 24 24">
              <polyline points="20 6 9 17 4 12" />
            </svg>
          ) : (
            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" strokeWidth="2.5" viewBox="0 0 24 24">
              <rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
              <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
            </svg>
          )}
        </button>
      </div>
      
      <input
        type="text"
        value={pathValue || ""}
        onChange={(e) => onChange(e.target.value)}
        title={pathValue || ""}
        className="py-2 px-3 text-[11px] font-mono settings-path-input input-premium"
        style={{
          "--focused-border": found ? "#10b981" : "#ef4444",
          "--focused-glow": found ? "rgba(16, 185, 129, 0.25)" : "rgba(239, 68, 68, 0.25)"
        } as any}
      />
    </div>
  );
}

export default function App() {
  const [activeTab, setActiveTab] = useState<string>("dashboard");
  const [downloads, setDownloads] = useState<DownloadTask[]>([]);
  const [connected, setConnected] = useState<boolean>(false);
  const [status, setStatus] = useState<AppStatus | null>(null);
  const [toast, setToast] = useState<{message: string; type: "success" | "error" | "info"} | null>(null);
  const [toastKey, setToastKey] = useState<number>(0);

  // HRTi inline download modal (replaces native prompt)
  const [hrtiModal, setHrtiModal] = useState<{refId: string; title: string} | null>(null);
  const [hrtiModalTitle, setHrtiModalTitle] = useState<string>("");

  // Log modal copy state
  const [logCopied, setLogCopied] = useState<boolean>(false);
  const [logFullscreen, setLogFullscreen] = useState<boolean>(false);
  
  // Terminal Logs Modal
  const [showLogModal, setShowLogModal] = useState<boolean>(false);
  const [selectedTask, setSelectedTask] = useState<DownloadTask | null>(null);
  // Bug 1 Fix: Use ref to avoid WS reconnection when selectedTask changes
  const selectedTaskRef = useRef<DownloadTask | null>(null);
  const logEndRef = useRef<HTMLDivElement>(null);

  // Global Config Form State
  const [outputDir, setOutputDir] = useState<string>("");
  const [binariesPaths, setBinariesPaths] = useState<Record<string, string>>({
    ffmpeg: "",
    mkvmerge: "",
    mp4decrypt: "",
    aria2c: "",
    device_wvd: ""
  });

  // Services Forms credentials
  const [voyoEmail, setVoyoEmail] = useState<string>("");
  const [voyoPassword, setVoyoPassword] = useState<string>("");

  const [hrtiEmail, setHrtiEmail] = useState<string>("");
  const [hrtiPassword, setHrtiPassword] = useState<string>("");

  const [eonUsername, setEonUsername] = useState<string>("");
  const [eonPassword, setEonPassword] = useState<string>("");
  const [eonSerial, setEonSerial] = useState<string>("");
  const [eonNumber, setEonNumber] = useState<string>("");

  const [rtsEmail, setRtsEmail] = useState<string>("");
  const [rtsPassword, setRtsPassword] = useState<string>("");

  const [hboMarket, setHboMarket] = useState<string>("emea");

  // Eye-toggle visibility states for credentials
  const [showVoyoPass, setShowVoyoPass] = useState<boolean>(false);
  const [showHrtiPass, setShowHrtiPass] = useState<boolean>(false);
  const [showEonPass, setShowEonPass] = useState<boolean>(false);
  const [showRtsPass, setShowRtsPass] = useState<boolean>(false);

  // Voyo Tab Form State
  const [voyoMode, setVoyoMode] = useState<"video" | "series">("video");
  const [voyoTarget, setVoyoTarget] = useState<string>("");
  const [voyoRes, setVoyoRes] = useState<string>("1080p");
  const [voyoSeriesData, setVoyoSeriesData] = useState<VoyoSeriesInfo | null>(null);
  const [voyoSearching, setVoyoSearching] = useState<boolean>(false);
  const [selectedVoyoEpisodes, setSelectedVoyoEpisodes] = useState<number[]>([]);
  const [voyoEpisodesRange, setVoyoEpisodesRange] = useState<string>("");

  // HRTi Tab visual catalog State
  const [hrtiCats, setHrtiCats] = useState<string[]>([]);
  const [selectedCat, setSelectedCat] = useState<string>("");
  const [catItems, setCatItems] = useState<HrtiItem[]>([]);
  const [catPage, setCatPage] = useState<number>(1);
  const [catTotalPages, setCatTotalPages] = useState<number>(1);
  const [hrtiSearchQuery, setHrtiSearchQuery] = useState<string>("");
  const [hrtiLoadingItems, setHrtiLoadingItems] = useState<boolean>(false);
  const hrtiDownloadWorkers = 16;
  const [selectedHrtiSeries, setSelectedHrtiSeries] = useState<{id: string; title: string} | null>(null);

  // EON Tab Form State
  const [eonMode, setEonMode] = useState<"vod" | "series" | "live">("vod");
  const [eonLiveInputMode, setEonLiveInputMode] = useState<"catalog" | "url">("catalog");
  const [saveFeedback, setSaveFeedback] = useState<boolean>(false);
  const [eonTarget, setEonTarget] = useState<string>("");
  const [eonDuration, setEonDuration] = useState<number>(3600); // F5: 1h default
  const [eonEpisodesRange, setEonEpisodesRange] = useState<string>("");
  const [eonPlay, setEonPlay] = useState<boolean>(false);
  const [eonPlayerPath, setEonPlayerPath] = useState<string>("");
  const [eonChannels, setEonChannels] = useState<string[]>([]);
  const [eonSearchQuery, setEonSearchQuery] = useState<string>("");
  const [eonSearchResults, setEonSearchResults] = useState<EonMediaItem[]>([]);
  const [eonEpgItems, setEonEpgItems] = useState<EonMediaItem[]>([]);

  // RTS Planeta Tab Form State
  const [rtsTarget, setRtsTarget] = useState<string>("");
  const [rtsStartEp, setRtsStartEp] = useState<string>("");
  const [rtsEndEp, setRtsEndEp] = useState<string>("");
  const [rtsVerbose, setRtsVerbose] = useState<boolean>(false);

  // HBO Max Tab Form State
  const [hboTarget, setHboTarget] = useState<string>("");
  const [hboSubs, setHboSubs] = useState<string>("sr,hr,mk,bs,sl");
  const [hboDirectMode, setHboDirectMode] = useState<boolean>(false);
  const [hboManifestUrl, setHboManifestUrl] = useState<string>("");
  const [hboLicenseUrl, setHboLicenseUrl] = useState<string>("");
  const [hboDirectTitle, setHboDirectTitle] = useState<string>("");
  const [hboDirectSubs, setHboDirectSubs] = useState<string>("sr,hr,mk,bs,sl");


  // Smart Dashboard Form State
  const [smartUrl, setSmartUrl] = useState<string>("");
  const [smartLoading, setSmartLoading] = useState<boolean>(false);
  const [smartData, setSmartData] = useState<any | null>(null);
  const [smartSelectedEpisodes, setSmartSelectedEpisodes] = useState<any[]>([]);
  const [smartEpisodesRange, setSmartEpisodesRange] = useState<string>("");
  const [smartResolution, setSmartResolution] = useState<string>("1080p");
  const [smartSubs, setSmartSubs] = useState<string>("sr,hr,mk,bs,sl");
  const [smartRtsVerbose, setSmartRtsVerbose] = useState<boolean>(false);

  // Session Import Form State
  const [importService, setImportService] = useState<string>("voyo");
  const [importSessionData, setImportSessionData] = useState<string>("");
  const [importLoading, setImportLoading] = useState<boolean>(false);

  const handleSmartDetect = async (urlStr: string) => {
    const val = urlStr.trim();
    if (!val) return;
    setSmartLoading(true);
    setSmartData(null);
    setSmartSelectedEpisodes([]);
    try {
      const res = await fetch(`${getApiHost()}/api/smart-detect?url=${encodeURIComponent(val)}`);
      const data = await res.json();
      if (res.ok) {
        setSmartData(data);
        // Auto-select all episodes by default
        if (data.episodes && data.episodes.length > 0) {
          setSmartSelectedEpisodes(data.episodes.map((ep: any) => ep.id));
        }
        showToast("Link uspešno prepoznat i analiziran!", "success");
      } else {
        showToast(data.detail || "URL nije prepoznat.", "error");
      }
    } catch (e) {
      showToast(errorMessage(e, "Greška na serveru"), "error");
    } finally {
      setSmartLoading(false);
    }
  };

  const startSmartDownload = async () => {
    if (!smartData) return;
    try {
      showToast("Pokretanje pametnog preuzimanja...", "info");
      let res: Response;

      // Build episodes range from selected episode IDs if no manual range
      let epRange = smartEpisodesRange;
      if (!epRange && smartSelectedEpisodes.length > 0 && smartData.episodes) {
        const indices = smartData.episodes
          .map((ep: any, idx: number) => smartSelectedEpisodes.includes(ep.id) ? idx + 1 : -1)
          .filter((i: number) => i !== -1);
        if (indices.length > 0 && indices.length < smartData.episodes.length) {
          epRange = indices.join(",");
        }
      }
      
      if (smartData.service === "voyo") {
        res = await fetch(`${getApiHost()}/api/voyo/download`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            target: smartData.target_id,
            mode: smartData.mode,
            episodes: epRange,
            resolution: smartResolution
          })
        });
      } else if (smartData.service === "hrti") {
        // HRTi: batch queue selected episodes by refId
        if (smartData.episodes && smartSelectedEpisodes.length > 0) {
          const selectedEps = smartData.episodes.filter((ep: any) => smartSelectedEpisodes.includes(ep.id));
          let allOk = true;
          for (const ep of selectedEps) {
            const r = await fetch(`${getApiHost()}/api/hrti/download`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ ref_id: ep.id, title: ep.title, workers: 16 })
            });
            if (!r.ok) allOk = false;
          }
          const data = { ok: allOk };
          if (allOk) {
            showToast(`${selectedEps.length} epizoda uspešno dodato u red!`, "success");
            setSmartUrl(""); setSmartData(null); setSmartSelectedEpisodes([]);
          } else {
            showToast("Neke epizode nisu mogle biti dodate.", "error");
          }
          if (!data) return;
          return;
        }
        res = await fetch(`${getApiHost()}/api/hrti/download`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            ref_id: smartData.target_id,
            title: smartData.title,
            workers: 16
          })
        });
      } else if (smartData.service === "eon") {
        res = await fetch(`${getApiHost()}/api/eon/download`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            mode: smartData.mode,
            target: smartData.target_id,
            episodes: epRange
          })
        });
      } else if (smartData.service === "rts" || smartData.service === "rtsplaneta") {
        const start = smartEpisodesRange ? parseInt(smartEpisodesRange.split("-")[0]) : undefined;
        const end = smartEpisodesRange ? parseInt(smartEpisodesRange.split("-")[1]) : undefined;
        res = await fetch(`${getApiHost()}/api/rts/download`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            target_url: smartUrl,
            start_ep: start,
            end_ep: end,
            verbose: smartRtsVerbose
          })
        });
      } else if (smartData.service === "hbomax") {
        res = await fetch(`${getApiHost()}/api/hbo/download`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            video_id: smartData.target_id,
            subs: smartSubs
          })
        });
      } else {
        showToast("Nepoznat servis za pametno preuzimanje.", "error");
        return;
      }

      const data = await res!.json();
      if (res!.ok) {
        showToast("Preuzimanje uspešno dodato u red!", "success");
        setSmartUrl("");
        setSmartData(null);
        setSmartSelectedEpisodes([]);
      } else {
        showToast(data.detail || "Greška pri pokretanju preuzimanja.", "error");
      }
    } catch (e) {
      showToast(errorMessage(e, "Greška na serveru"), "error");
    }
  };

  const handleImportSession = async () => {
    if (!importSessionData.trim()) {
      showToast("Nalepite podatke sesije pre uvoza.", "error");
      return;
    }
    setImportLoading(true);
    try {
      const res = await fetch(`${getApiHost()}/api/config/import-session`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          service: importService,
          session_data: importSessionData
        })
      });
      const data = await res.json();
      if (res.ok) {
        showToast(data.message || "Sesija uspešno uvezena!", "success");
        setImportSessionData("");
        fetchStatus();
      } else {
        showToast(data.detail || "Greška pri uvozu sesije.", "error");
      }
    } catch (e) {
      showToast(errorMessage(e, "Greška na serveru"), "error");
    } finally {
      setImportLoading(false);
    }
  };

  // F1: Confirm clear queue
  const [confirmClear, setConfirmClear] = useState<boolean>(false);

  const showToast = (message: string, type: "success" | "error" | "info" = "success") => {
    setToastKey(k => k + 1);
    setToast({ message, type });
    setTimeout(() => setToast(null), 5000);
  };

  const getApiHost = () =>
    window.location.hostname === "localhost" ? "http://localhost:8000" : "";

  // Fetch Status and Settings on Load
  const fetchStatus = async () => {
    try {
      const res = await fetch(`${getApiHost()}/api/status`);
      if (res.ok) {
        const data: AppStatus = await res.json();
        setStatus(data);
        setOutputDir(data.output_dir);
        const paths: Record<string, string> = {};
        for (const [name, info] of Object.entries(data.binaries)) {
          paths[name] = info.path;
        }
        setBinariesPaths(paths);
      }
    } catch (e) {
      console.error("Failed to fetch system status:", e);
    }
  };

  useEffect(() => {
    fetchStatus();
  }, []);

  useEffect(() => {
    const eon = status?.services.eon;
    if (!eon) return;
    if (!eonUsername && eon.username) setEonUsername(eon.username);
    if (!eonSerial && eon.serial) setEonSerial(eon.serial);
    if (!eonNumber && eon.number) setEonNumber(eon.number);
  }, [status, eonUsername, eonSerial, eonNumber]);

  // Bug 1 Fix: Keep selectedTaskRef in sync without it being in WS dependency array
  useEffect(() => {
    selectedTaskRef.current = selectedTask;
  }, [selectedTask]);

  // Bug 1 Fix: WebSocket connects ONCE — no selectedTask in dependency array
  useEffect(() => {
    let ws: WebSocket;
    const connect = () => {
      const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
      const host = window.location.hostname === "localhost" ? "localhost:8000" : window.location.host;
      ws = new WebSocket(`${protocol}//${host}/ws`);

      ws.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data);
          if (payload.type === "queue_update") {
            setDownloads(payload.data);
            // Use ref instead of closure over selectedTask to avoid WS reconnect
            if (selectedTaskRef.current) {
              const updated = payload.data.find((d: DownloadTask) => d.id === selectedTaskRef.current!.id);
              if (updated) {
                setSelectedTask(updated);
              }
            }
          }
        } catch (e) {
          console.error("Failed to parse WS payload:", e);
        }
      };

      ws.onclose = () => {
        setConnected(false);
        setTimeout(connect, 3000);
      };

      ws.onopen = () => {
        setConnected(true);
      };
    };

    connect();
    return () => {
      if (ws) ws.close();
    };
  }, []); // ✅ Empty dependency array — WS connects once

  // Scroll to bottom of logs
  useEffect(() => {
    if (logEndRef.current) {
      logEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [selectedTask?.logs]);

  // Fetch EON Channels & HRTi Categories when tabs are selected
  useEffect(() => {
    if (activeTab === "hrti" && hrtiCats.length === 0) {
      fetchHrtiCategories();
    }
    if (activeTab === "eon" && eonChannels.length === 0) {
      fetchEonChannels();
    }
  }, [activeTab]);

  // ── API Operations ─────────────────────────────────────────────────────────

  const handleSaveConfig = async () => {
    try {
      const res = await fetch(`${getApiHost()}/api/config`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ output_dir: outputDir, binaries: binariesPaths })
      });
      if (res.ok) {
        showToast("Podešavanja uspešno sačuvana!");
        setSaveFeedback(true);
        setTimeout(() => setSaveFeedback(false), 2500);
        fetchStatus();
      } else {
        showToast("Greška pri čuvanju podešavanja", "error");
      }
    } catch (e: any) {
      showToast(e.message || "Greška na serveru", "error");
    }
  };

  const handleSaveDeviceWvdPath = async () => {
    try {
      const res = await fetch(`${getApiHost()}/api/config`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ binaries: { device_wvd: binariesPaths.device_wvd || "" } })
      });
      if (res.ok) {
        showToast("Putanja do device.wvd je sacuvana.");
        fetchStatus();
      } else {
        const data = await res.json().catch(() => null);
        showToast(data?.detail || "Greska pri cuvanju device.wvd putanje", "error");
      }
    } catch (e: any) {
      showToast(e.message || "Greska na serveru", "error");
    }
  };

  const submitLogin = async (service: string, body: any) => {
    try {
      const res = await fetch(`${getApiHost()}/api/${service}/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body)
      });
      const data = await res.json();
      if (res.ok) {
        showToast(`Kredencijali za ${service.toUpperCase()} uspesno sacuvani!`);
        if (data.warning) {
          showToast(data.warning, "info");
        }
        fetchStatus();
      } else {
        showToast(data.detail || "Greška pri prijavi", "error");
      }
    } catch (e: any) {
      showToast(e.message || "Greška na serveru", "error");
    }
  };

  // Voyo specific
  const searchVoyoSeries = async () => {
    if (!voyoTarget) return;
    setVoyoSearching(true);
    setVoyoSeriesData(null);
    try {
      let seriesId = voyoTarget.trim();
      const m = seriesId.match(/_(\d+)\.html|Series_(\d+)/i);
      if (m) seriesId = m[1] || m[2];
      const res = await fetch(`${getApiHost()}/api/voyo/series/${seriesId}`);
      const data = await res.json();
      if (res.ok) {
        setVoyoSeriesData(data);
        setSelectedVoyoEpisodes(data.episodes.map((e: any) => e.id));
      } else {
        showToast(data.detail || "Neuspešno učitavanje serije", "error");
      }
    } catch (e: any) {
      showToast(e.message || "Greška na serveru", "error");
    } finally {
      setVoyoSearching(false);
    }
  };

  const startVoyoDownload = async () => {
    try {
      let epRange = voyoEpisodesRange;
      if (voyoMode === "series" && voyoSeriesData && !epRange) {
        const indices = voyoSeriesData.episodes
          .map((ep, idx) => selectedVoyoEpisodes.includes(ep.id) ? idx + 1 : -1)
          .filter(idx => idx !== -1);
        if (indices.length === 0) {
          showToast("Morate selektovati barem jednu epizodu!", "error");
          return;
        }
        epRange = indices.join(",");
      }

      const res = await fetch(`${getApiHost()}/api/voyo/download`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ target: voyoTarget, mode: voyoMode, episodes: epRange, resolution: voyoRes })
      });
      if (res.ok) {
        showToast("Preuzimanje dodato u red!");
        setVoyoTarget("");
        setVoyoSeriesData(null);
      } else {
        showToast("Greška pri slanju zahteva", "error");
      }
    } catch (e: any) {
      showToast(e.message || "Greška na serveru", "error");
    }
  };

  // HRTi specific
  const fetchHrtiCategories = async () => {
    try {
      const res = await fetch(`${getApiHost()}/api/hrti/categories`);
      if (res.ok) {
        const data = await res.json();
        setHrtiCats(data);
        if (data.length > 0) {
          setSelectedCat(data[0]);
          fetchHrtiCategoryItems(data[0], 1);
        }
      }
    } catch (e) { console.error(e); }
  };

  const fetchHrtiCategoryItems = async (cat: string, page: number = 1) => {
    setHrtiLoadingItems(true);
    setSelectedHrtiSeries(null);
    try {
      const res = await fetch(`${getApiHost()}/api/hrti/category-items?category=${cat}&page=${page}`);
      if (res.ok) {
        const data = await res.json();
        setCatItems(data.items);
        setCatPage(data.metadata.page);
        setCatTotalPages(data.metadata.total_pages);
      }
    } catch (e) { console.error(e); }
    finally { setHrtiLoadingItems(false); }
  };

  const searchHrti = async () => {
    if (!hrtiSearchQuery.trim()) return;
    setHrtiLoadingItems(true);
    setSelectedHrtiSeries(null);
    try {
      const res = await fetch(`${getApiHost()}/api/hrti/search?query=${encodeURIComponent(hrtiSearchQuery)}`);
      if (res.ok) {
        const data = await res.json();
        setCatItems(data.items);
        setCatPage(1);
        setCatTotalPages(1);
      }
    } catch (e) { console.error(e); }
    finally { setHrtiLoadingItems(false); }
  };

  const fetchHrtiSeriesEpisodes = async (uuid: string, title: string) => {
    setHrtiLoadingItems(true);
    setSelectedHrtiSeries({ id: uuid, title });
    try {
      const res = await fetch(`${getApiHost()}/api/hrti/series/${uuid}`);
      if (res.ok) {
        const data = await res.json();
        setCatItems(data.items);
        setCatPage(1);
        setCatTotalPages(1);
      }
    } catch (e) { console.error(e); }
    finally { setHrtiLoadingItems(false); }
  };

  const startHrtiDownload = (refId: string, itemTitle: string) => {
    // Open inline modal instead of native prompt()
    setHrtiModalTitle(itemTitle);
    setHrtiModal({ refId, title: itemTitle });
  };

  const confirmHrtiDownload = async () => {
    if (!hrtiModal) return;
    try {
      const res = await fetch(`${getApiHost()}/api/hrti/download`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ref_id: hrtiModal.refId, title: hrtiModalTitle || hrtiModal.title, workers: hrtiDownloadWorkers })
      });
      if (res.ok) {
        showToast("HRTi preuzimanje pokrenuto!");
      } else {
        showToast("Greška pri slanju preuzimanja", "error");
      }
    } catch (e: any) {
      showToast(e.message || "Greška na serveru", "error");
    } finally {
      setHrtiModal(null);
      setHrtiModalTitle("");
    }
  };

  // EON specific
  const fetchEonChannels = async () => {
    try {
      const res = await fetch(`${getApiHost()}/api/eon/channels`);
      const data = await res.json().catch(() => null);
      if (res.ok) {
        setEonChannels(Array.isArray(data) ? data : []);
      } else {
        setEonChannels([]);
        if (activeTab === "eon") {
          showToast(data?.detail || "EON engine nije spreman.", "error");
        }
      }
    } catch (e) { console.error(e); }
  };

  const startEonDownload = async () => {
    try {
      const res = await fetch(`${getApiHost()}/api/eon/download`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          mode: eonMode, target: eonTarget, duration: eonDuration,
          episodes: eonEpisodesRange, play: eonPlay, player_path: eonPlayerPath
        })
      });
      const data = await res.json().catch(() => null);
      if (res.ok) {
        showToast("EON download zadatak uspešno poslat!");
        setEonTarget("");
      } else {
        showToast(data?.detail || "Greška pri slanju zadatka", "error");
      }
    } catch (e: any) {
      showToast(e.message || "Greška na serveru", "error");
    }
  };

  const searchEonVod = async () => {
    if (!eonSearchQuery.trim()) return;
    try {
      const res = await fetch(`${getApiHost()}/api/eon/search?query=${encodeURIComponent(eonSearchQuery.trim())}`);
      const data = await res.json().catch(() => null);
      if (res.ok) {
        setEonSearchResults(Array.isArray(data) ? data : []);
        if (!Array.isArray(data) || data.length === 0) {
          showToast("Nema EON VOD rezultata u konfigurisanom API/lokalnom katalogu.", "info");
        }
      } else {
        showToast(data?.detail || "EON pretraga nije uspela", "error");
      }
    } catch (e: any) {
      showToast(e.message || "Greška na serveru", "error");
    }
  };

  const fetchEonEpg = async () => {
    if (!eonTarget) return;
    try {
      const res = await fetch(`${getApiHost()}/api/eon/epg?channel=${encodeURIComponent(eonTarget)}`);
      const data = await res.json().catch(() => null);
      if (res.ok) {
        setEonEpgItems(Array.isArray(data) ? data : []);
        if (!Array.isArray(data) || data.length === 0) {
          showToast("Nema EPG zapisa za izabrani kanal.", "info");
        }
      } else {
        showToast(data?.detail || "EON EPG nije dostupan", "error");
      }
    } catch (e: any) {
      showToast(e.message || "Greška na serveru", "error");
    }
  };

  const initEonCatalogs = async () => {
    try {
      const res = await fetch(`${getApiHost()}/api/eon/catalogs/init`, { method: "POST" });
      const data = await res.json().catch(() => null);
      if (res.ok) {
        const created = data?.created?.length ?? 0;
        showToast(created ? "EON katalog fajlovi su napravljeni." : "EON katalog fajlovi već postoje.", "success");
        fetchEonChannels();
      } else {
        showToast(data?.detail || "Greška pri kreiranju EON kataloga", "error");
      }
    } catch (e: any) {
      showToast(e.message || "Greška na serveru", "error");
    }
  };

  const loginEonApi = async () => {
    if (!eonUsername || !eonPassword || !eonSerial || !eonNumber) {
      showToast("Popunite EON nalog, lozinku, device serial i device number.", "error");
      return;
    }
    try {
      const res = await fetch(`${getApiHost()}/api/eon/api-login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username: eonUsername, password: eonPassword, serial: eonSerial, number: eonNumber })
      });
      const data = await res.json().catch(() => null);
      if (res.ok) {
        showToast(data?.tokens_saved ? "EON API token je sačuvan." : "API login je prošao, ali token nije pronađen u odgovoru.", data?.tokens_saved ? "success" : "info");
        fetchStatus();
      } else {
        showToast(data?.detail || "EON API login nije uspeo", "error");
      }
    } catch (e: any) {
      showToast(e.message || "Greška na serveru", "error");
    }
  };

  const refreshEonApiToken = async () => {
    try {
      const res = await fetch(`${getApiHost()}/api/eon/refresh-token`, { method: "POST" });
      const data = await res.json().catch(() => null);
      if (res.ok) {
        showToast(data?.tokens_saved ? "EON API token je osvežen." : "Refresh je prošao, ali token nije pronađen u odgovoru.", data?.tokens_saved ? "success" : "info");
        fetchStatus();
      } else {
        showToast(data?.detail || "EON token refresh nije uspeo", "error");
      }
    } catch (e: any) {
      showToast(e.message || "Greška na serveru", "error");
    }
  };

  // RTS specific
  const startRtsDownload = async () => {
    try {
      const res = await fetch(`${getApiHost()}/api/rts/download`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          target_url: rtsTarget,
          start_ep: rtsStartEp ? parseInt(rtsStartEp) : null,
          end_ep: rtsEndEp ? parseInt(rtsEndEp) : null,
          verbose: rtsVerbose
        })
      });
      if (res.ok) {
        showToast("RTS Planeta preuzimanje dodato!");
        setRtsTarget("");
      } else {
        showToast("Greška pri slanju zadatka", "error");
      }
    } catch (e: any) {
      showToast(e.message || "Greška na serveru", "error");
    }
  };

  // HBO specific
  const startHboLogin = async () => {
    try {
      const res = await fetch(`${getApiHost()}/api/hbo/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ market: hboMarket })
      });
      if (res.ok) {
        showToast("Pokrenuta HBO Max prijava! Otvorite terminal/logs da vidite kod.");
      } else {
        showToast("Neuspešno pokretanje prijave", "error");
      }
    } catch (e: any) {
      showToast(e.message || "Greška na serveru", "error");
    }
  };

  const startHboDownload = async () => {
    try {
      const res = await fetch(`${getApiHost()}/api/hbo/download`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ video_id: hboTarget, subs: hboSubs })
      });
      if (res.ok) {
        showToast("HBO Max preuzimanje pokrenuto!");
        setHboTarget("");
      } else {
        showToast("Greška pri slanju zadatka", "error");
      }
    } catch (e: any) {
      showToast(e.message || "Greška na serveru", "error");
    }
  };

  const startHboDirectDownload = async () => {
    if (!hboManifestUrl.trim() || !hboLicenseUrl.trim()) {
      showToast("Unesite i Manifest URL i License URL", "error");
      return;
    }
    try {
      const res = await fetch(`${getApiHost()}/api/hbo/download-direct`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          manifest_url: hboManifestUrl.trim(),
          license_url: hboLicenseUrl.trim(),
          title: hboDirectTitle.trim(),
          subs: hboDirectSubs,
        })
      });
      if (res.ok) {
        showToast("HBO Max Direct preuzimanje pokrenuto! ✓");
        setHboManifestUrl("");
        setHboLicenseUrl("");
        setHboDirectTitle("");
      } else {
        const err = await res.json().catch(() => ({}));
        showToast(err?.detail || "Greška pri slanju zadatka", "error");
      }
    } catch (e: any) {
      showToast(e.message || "Greška na serveru", "error");
    }
  };

  // Queue actions
  const cancelDownloadTask = async (id: string) => {
    try {
      await fetch(`${getApiHost()}/api/queue/cancel`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id })
      });
      showToast("Slanje zahteva za otkazivanje...", "info");
    } catch (e) { console.error(e); }
  };

  const retryDownloadTask = async (id: string) => {
    try {
      const res = await fetch(`${getApiHost()}/api/queue/retry`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id })
      });
      if (res.ok) {
        showToast("Preuzimanje ponovo pokrenuto!", "success");
      } else {
        const err = await res.json().catch(() => ({}));
        showToast(err?.detail || "Nije moguće pokrenuti ponovo.", "error");
      }
    } catch (e) {
      showToast("Greška na serveru", "error");
    }
  };

  const clearCompletedQueue = async () => {
    try {
      await fetch(`${getApiHost()}/api/queue/clear`, { method: "POST" });
      showToast("Očišćen red preuzimanja!");
      setConfirmClear(false);
    } catch (e) { console.error(e); }
  };

  // Computed
  const activeDownloadsCount = downloads.filter(d => d.status === "downloading" || d.status === "pending").length;
  const eonStatus = status?.services.eon;
  const eonReady = Boolean(eonStatus?.ready);
  const eonMissing = eonStatus?.missing ?? [];
  const eonOptionalMissing = eonStatus?.optional_missing ?? [];
  const deviceWvdInfo = status?.binaries.device_wvd;
  const eonRootPath = eonStatus?.script_path
    ? eonStatus.script_path.replace(/[\\/]+eon_downloader\.py$/i, "")
    : "root aplikacije";
  const eonCatalogPath = (name: string) => (
    eonRootPath === "root aplikacije" ? name : `${eonRootPath}\\${name}`
  );

  return (
    <div className="flex w-full min-h-screen">
      
      {/* Toast — type-based glow + progress bar */}
      {toast && (
        <div className={`fixed top-6 right-6 z-50 flex items-center gap-3 px-5 py-4 rounded-lg glass-panel animate-slide overflow-hidden ${
          toast.type === "error" ? "glow-red" : toast.type === "success" ? "glow-emerald" : "glow-indigo"
        }`} style={{paddingBottom: "1.25rem"}}>
          {toast.type === "success" && <CheckCircle2 className="w-5 h-5 text-emerald-400 flex-shrink-0" />}
          {toast.type === "error" && <AlertCircle className="w-5 h-5 text-red-400 flex-shrink-0" />}
          {toast.type === "info" && <Info className="w-5 h-5 text-indigo-400 flex-shrink-0" />}
          <span className="text-sm font-medium">{toast.message}</span>
          {/* Progress bar — auto-dismiss indicator */}
          <div key={toastKey} className={`toast-progress toast-progress-${toast.type}`} />
        </div>
      )}

      {/* ── LEFT SIDEBAR ── */}
      <aside className="w-64 glass-panel border-r border-glass flex flex-col justify-between p-6 bg-gradient-to-b from-[#11121c] to-[#0a0b10]">
        <div>
          {/* Logo */}
          <div className="flex items-center gap-3 mb-10 group cursor-pointer">
            <div className="w-11 h-11 rounded-xl bg-gradient-to-tr from-indigo-600 via-indigo-500 to-purple-600 flex items-center justify-center glow-indigo shadow-lg transition-all duration-300 group-hover:scale-105 group-hover:shadow-[0_0_20px_rgba(99,102,241,0.5)]">
              <Download className="w-5 h-5 text-white transition-transform duration-500 group-hover:rotate-12 group-hover:scale-110" />
            </div>
            <div>
              <h1 className="font-extrabold text-sm tracking-wider text-white bg-clip-text bg-gradient-to-r from-white via-slate-100 to-slate-300">o0o0o0o-downloader</h1>
              <p className="text-[9px] text-indigo-400 font-black tracking-widest uppercase">Premium Downloader</p>
            </div>
          </div>

          {/* Navigation with per-service active colors + download count badge */}
          <nav className="flex flex-col gap-2">
            {SERVICE_META.map((tab) => {
              const Icon = tab.icon;
              const active = activeTab === tab.id;
              // Fix: hbo tab counts hbomax service downloads
              const svcFilter = tab.id === "hbo" ? "hbomax" : tab.id;
              const svcCount = tab.id !== "settings"
                ? downloads.filter(d => d.service === svcFilter && (d.status === "downloading" || d.status === "pending")).length
                : 0;
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  style={active ? {boxShadow: `0 4px 14px ${tab.activeGlow}`} : {}}
                  className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg text-sm font-semibold transition-all duration-200 ${
                    active
                      ? `${tab.activeBg} text-white`
                      : "text-text-secondary hover:bg-white/[0.03] hover:text-white"
                  }`}
                >
                  <Icon className={`w-4 h-4 flex-shrink-0 ${active ? "text-white" : tab.colorClass}`} />
                  <span className="flex-1 text-left">{tab.label}</span>
                  {/* V6: download count badge */}
                  {svcCount > 0 && (
                    <span className="nav-badge">{svcCount}</span>
                  )}
                </button>
              );
            })}
          </nav>
        </div>

        {/* WebSocket Status Indicator */}
        <div className="flex flex-col gap-2 p-4 rounded-xl bg-black/40 border border-white/[0.04] shadow-inner">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Server className="w-3.5 h-3.5 text-text-muted" />
              <span className="text-[11px] text-text-secondary font-bold uppercase tracking-wider">Sistem Status</span>
            </div>
            <span className={`text-[10px] font-black uppercase px-2 py-0.5 rounded-full ${connected ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20" : "bg-red-500/10 text-red-400 border border-red-500/20 animate-pulse"}`}>
              {connected ? "OK" : "Error"}
            </span>
          </div>
          <div className="flex items-center justify-between border-t border-white/[0.03] pt-2">
            <span className="text-[10px] text-text-muted">Veza sa serverom:</span>
            <span className="flex items-center gap-1.5 text-xs font-extrabold text-white">
              <span className={`w-2 h-2 rounded-full ${connected ? "bg-emerald-400 shadow-[0_0_8px_#34d399]" : "bg-red-400 shadow-[0_0_8px_#f87171] animate-ping"}`}></span>
              {connected ? "Aktivan" : "U prekidu"}
            </span>
          </div>
        </div>
      </aside>

      {/* ── MAIN CONTENT AREA ── */}
      {/* V8: key on main wrapper forces re-animation on tab change */}
      <main className="flex-1 p-10 overflow-y-auto max-h-screen">
        
        {/* PAMETNO PREUZIMANJE DASHBOARD */}
        {activeTab === "dashboard" && (() => {
          // Service theme config
          const SVC_THEMES: Record<string, {emoji:string; name:string; color:string; glow:string; example:string; exampleLabel:string}> = {
            voyo:    { emoji:"🟠", name:"Voyo RS",     color:"#f97316", glow:"rgba(249,115,22,0.08)",   example:"https://voyo.rs/uspeh-1_50584.html", exampleLabel:"Film (video ID)" },
            hrti:    { emoji:"🔵", name:"HRTi",        color:"#06b6d4", glow:"rgba(6,182,212,0.08)",    example:"https://hrti.hrt.hr/video/show/4a3b2c1d-0000-0000-0000-000000000001", exampleLabel:"Video (UUID)" },
            eon:     { emoji:"🟢", name:"EON TV",      color:"#10b981", glow:"rgba(16,185,129,0.08)",   example:"https://eon.tv/player/vod-abc123", exampleLabel:"VOD naslov" },
            rts:     { emoji:"🔴", name:"RTS Planeta", color:"#f43f5e", glow:"rgba(244,63,94,0.08)",    example:"https://www.rtsplaneta.rs/video/show/12345", exampleLabel:"Epizoda/emisija" },
            hbomax:  { emoji:"🟣", name:"HBO Max",     color:"#9333ea", glow:"rgba(147,51,234,0.08)",   example:"https://www.max.com/show/urn:hbo:episode:xyz123", exampleLabel:"Epizoda/film" },
          };
          const svcKeys = Object.keys(SVC_THEMES);
          // Service auth sub-text (from status if available)
          const getSvcStatus = (k: string) => {
            const s = status?.services;
            if (!s) return { online: false, label: "Nije podešeno" };
            const svc = s[k === "rts" ? "rtsplaneta" : k];
            if (!svc) return { online: false, label: "Nije podešeno" };
            const authenticated = (svc as any).authenticated || (svc as any).ready;
            const email = (svc as any).email || (svc as any).username || (svc as any).nickname || "";
            return { online: !!authenticated, label: email ? email : (authenticated ? "Aktivan" : "Nije podešeno") };
          };
          // Preview panel service theme
          const previewTheme = smartData ? SVC_THEMES[smartData.service] ?? SVC_THEMES.voyo : null;

          return (
          <div key="dashboard" className="tab-content">
            {/* Tab header */}
            <div className="tab-page-header tab-header-dash mb-6">
              <div className="tab-page-header-icon" style={{background:"linear-gradient(135deg,#f59e0b,#d97706)"}}>
                <Zap style={{width:24,height:24,color:"white"}} />
              </div>
              <div style={{flex:1}}>
                <h2 className="text-2xl font-extrabold text-white mb-1 flex items-center gap-2.5">
                  <Zap className="w-6 h-6 text-amber-400" /> Pametno Preuzimanje
                </h2>
                <p className="text-text-secondary text-sm">Unesite URL adresu za automatsko prepoznavanje i preuzimanje videa sa podržanih servisa.</p>
              </div>
            </div>

            {/* ── Service Status Cards Grid ── */}
            <div className="smart-svc-grid">
              {svcKeys.map(k => {
                const t = SVC_THEMES[k];
                const st = getSvcStatus(k);
                return (
                  <div
                    key={k}
                    className="smart-svc-card"
                    style={{ "--svc-glow": t.glow, "--svc-color": t.color, borderColor: st.online ? `${t.color}30` : "rgba(255,255,255,0.07)" } as any}
                    onClick={() => { setSmartUrl(t.example); handleSmartDetect(t.example); }}
                  >
                    <div className="smart-svc-card-top">
                      <span className="smart-svc-emoji">{t.emoji}</span>
                      <span className={`smart-svc-dot ${st.online ? "online" : "offline"}`} />
                    </div>
                    <div className="smart-svc-name">{t.name}</div>
                    <div className="smart-svc-email">{st.label}</div>
                    <button
                      className="smart-svc-try-btn"
                      style={{ "--svc-color": t.color } as any}
                      onClick={e => { e.stopPropagation(); setSmartUrl(t.example); handleSmartDetect(t.example); }}
                    >
                      ▶ Probaj primer
                    </button>
                  </div>
                );
              })}
            </div>

            <div className="flex flex-col gap-5 max-w-4xl">
              {/* ── URL Input Bar ── */}
              <div>
                <label className="text-white font-semibold text-sm mb-2 block" style={{letterSpacing:"0.01em"}}>
                  Zalepite link za video, epizodu ili seriju
                </label>
                <div className="smart-url-wrap">
                  <input
                    type="text"
                    className={`smart-url-input ${smartUrl ? "has-value" : ""}`}
                    placeholder="npr. https://voyo.rs/uspeh-1_50584.html, hrti.hrt.hr, rtsplaneta.rs, eon.tv, max.com..."
                    value={smartUrl}
                    onChange={e => {
                      setSmartUrl(e.target.value);
                      if (e.target.value.trim().startsWith("http")) handleSmartDetect(e.target.value);
                    }}
                    onKeyDown={e => e.key === "Enter" && handleSmartDetect(smartUrl)}
                  />
                  {/* Clipboard paste btn */}
                  <button
                    className="smart-url-paste-btn"
                    title="Nalepi iz clipboard-a"
                    onClick={async () => {
                      try {
                        const text = await navigator.clipboard.readText();
                        if (text.trim().startsWith("http")) { setSmartUrl(text.trim()); handleSmartDetect(text.trim()); }
                        else showToast("Clipboard ne sadrži validan URL.", "error");
                      } catch { showToast("Dozvola za clipboard nije dozvoljena.", "error"); }
                    }}
                  >
                    <Copy style={{width:14,height:14}} />
                  </button>
                  <button
                    className="smart-url-analyze-btn"
                    onClick={() => handleSmartDetect(smartUrl)}
                    disabled={smartLoading || !smartUrl}
                  >
                    {smartLoading ? <Loader2 style={{width:16,height:16,animation:"spin 1s linear infinite"}} /> : <Search style={{width:16,height:16}} />}
                    {smartLoading ? "Analizira..." : "Analiziraj"}
                  </button>
                </div>
              </div>

              {/* ── Preview & Download Panel ── */}
              {smartData && previewTheme && (
                <div
                  className="smart-preview-panel"
                  style={{
                    borderColor: `${previewTheme.color}40`,
                    boxShadow: `0 0 40px ${previewTheme.glow}, 0 4px 24px rgba(0,0,0,0.4)`,
                  }}
                >
                  {/* Header */}
                  <div className="smart-preview-header" style={{borderBottom:"1px solid rgba(255,255,255,0.05)", paddingBottom:20}}>
                    <div className="smart-preview-thumb" style={{borderColor:`${previewTheme.color}30`}}>
                      {smartData.thumbnail
                        ? <img src={smartData.thumbnail} alt={smartData.title} />
                        : <span style={{fontSize:"2rem"}}>{previewTheme.emoji}</span>
                      }
                    </div>
                    <div style={{flex:1}}>
                      <div
                        className="smart-preview-badge"
                        style={{background:`${previewTheme.color}18`, color:previewTheme.color, border:`1px solid ${previewTheme.color}35`}}
                      >
                        {previewTheme.emoji} {previewTheme.name} · {smartData.mode?.toUpperCase()}
                      </div>
                      <h3 className="smart-preview-title">{smartData.title}</h3>
                      {smartData.description && <p className="smart-preview-desc">{smartData.description}</p>}
                    </div>
                  </div>

                  {/* Body */}
                  <div className="smart-preview-body">
                    {/* Episode checklist (series with episodes) */}
                    {smartData.episodes && smartData.episodes.length > 0 && (
                      <div>
                        <div style={{display:"flex", justifyContent:"space-between", alignItems:"center", marginBottom:10}}>
                          <label style={{margin:0}}>
                            Epizode ({smartSelectedEpisodes.length}/{smartData.episodes.length} odabrano)
                          </label>
                          <div style={{display:"flex", gap:12}}>
                            <button
                              style={{fontSize:"0.72rem", fontWeight:700, color:previewTheme.color, background:"none", border:"none", cursor:"pointer"}}
                              onClick={() => setSmartSelectedEpisodes(smartData.episodes.map((e:any)=>e.id))}
                            >Označi sve</button>
                            <span style={{color:"var(--text-muted)"}}>|</span>
                            <button
                              style={{fontSize:"0.72rem", fontWeight:700, color:"var(--text-muted)", background:"none", border:"none", cursor:"pointer"}}
                              onClick={() => setSmartSelectedEpisodes([])}
                            >Odznači sve</button>
                          </div>
                        </div>
                        <div className="smart-ep-list">
                          {smartData.episodes.map((ep: any, idx: number) => {
                            const checked = smartSelectedEpisodes.includes(ep.id);
                            return (
                              <div
                                key={ep.id ?? idx}
                                className={`smart-ep-item ${checked ? "selected" : ""}`}
                                onClick={() => setSmartSelectedEpisodes(checked
                                  ? smartSelectedEpisodes.filter((id:any) => id !== ep.id)
                                  : [...smartSelectedEpisodes, ep.id]
                                )}
                                style={checked ? {borderLeft:`3px solid ${previewTheme.color}80`} : {borderLeft:"3px solid transparent"}}
                              >
                                <div className={`custom-checkbox-box ${checked ? "checked" : ""}`} style={checked ? {background:previewTheme.color, borderColor:previewTheme.color} : {}}>
                                  <svg className="custom-checkbox-check" viewBox="0 0 10 10" fill="none" stroke="white" strokeWidth="2">
                                    <polyline points="1.5 5 4 7.5 8.5 2" />
                                  </svg>
                                </div>
                                {(ep.season && ep.episode) && (
                                  <span style={{fontSize:"0.72rem", fontWeight:800, color:previewTheme.color, minWidth:52, flexShrink:0}}>
                                    S{String(ep.season).padStart(2,"0")}E{String(ep.episode).padStart(2,"0")}
                                  </span>
                                )}
                                <span style={{flex:1, fontSize:"0.82rem", color:"white", overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap"}}>
                                  {ep.title}
                                </span>
                                {ep.length_mins > 0 && <span style={{fontSize:"0.7rem", color:"var(--text-muted)", flexShrink:0}}>{ep.length_mins}m</span>}
                                {ep.drm && <Lock style={{width:12,height:12,color:"#f59e0b",flexShrink:0}} />}
                              </div>
                            );
                          })}
                        </div>
                      </div>
                    )}

                    {/* Config row */}
                    <div className="smart-config-row">
                      {["voyo","eon"].includes(smartData.service) && (
                        <div>
                          <label>Rezolucija</label>
                          <CustomSelect
                            value={smartResolution}
                            options={["1080p", "720p", "480p"]}
                            onChange={(val) => setSmartResolution(val)}
                            formatLabel={(val) => val === "1080p" ? "1080p Full HD" : val === "720p" ? "720p HD" : "480p SD"}
                          />
                        </div>
                      )}
                      {smartData.service === "hbomax" && (
                        <div>
                          <label>Prevodi (jezici)</label>
                          <input type="text" value={smartSubs} onChange={e=>setSmartSubs(e.target.value)}
                            placeholder="sr,hr,mk,bs,sl"
                            className="py-2.5 px-3 bg-black/40 border border-glass text-white rounded focus:outline-none w-full" />
                        </div>
                      )}
                      {(smartData.mode === "series" && !smartData.episodes) && (
                        <div>
                          <label>Raspon epizoda (opciono)</label>
                          <input type="text" value={smartEpisodesRange} onChange={e=>setSmartEpisodesRange(e.target.value)}
                            placeholder="npr. 1-3 ili 2-"
                            className="py-2.5 px-3 bg-black/40 border border-glass text-white rounded focus:outline-none w-full" />
                          <p style={{fontSize:"0.68rem",color:"var(--text-muted)",marginTop:4}}>Ostavite prazno za sve epizode.</p>
                        </div>
                      )}
                      {["rts", "rtsplaneta"].includes(smartData.service) && (
                        <div className="flex items-center" style={{marginTop: 24}}>
                          <label className="custom-checkbox-wrap" style={{width: "100%"}}>
                            <input
                              type="checkbox"
                              checked={smartRtsVerbose}
                              onChange={e => setSmartRtsVerbose(e.target.checked)}
                            />
                            <div className={`custom-checkbox-box ${smartRtsVerbose ? "checked" : ""}`} style={smartRtsVerbose ? {background:"#f43f5e", borderColor:"#f43f5e"} : {}}>
                              <svg className="custom-checkbox-check" viewBox="0 0 10 10" fill="none" stroke="white" strokeWidth="2">
                                <polyline points="1.5 5 4 7.5 8.5 2" />
                              </svg>
                            </div>
                            <span className="text-sm font-semibold text-white">Verbose/Detaljan Log preuzimanja</span>
                          </label>
                        </div>
                      )}
                    </div>

                    {/* CTA */}
                    <div style={{display:"flex", alignItems:"center", gap:14}}>
                      <button
                        className={`smart-cta-btn smart-cta-${smartData.service}`}
                        onClick={startSmartDownload}
                        disabled={smartData.episodes && smartSelectedEpisodes.length === 0}
                      >
                        <Download style={{width:18,height:18}} />
                        {smartData.episodes
                          ? `Preuzmi ${smartSelectedEpisodes.length} epizod${smartSelectedEpisodes.length === 1 ? "u" : smartSelectedEpisodes.length < 5 ? "e" : "a"}`
                          : "Pokreni Preuzimanje"
                        }
                      </button>
                      <button
                        onClick={() => { setSmartData(null); setSmartUrl(""); setSmartSelectedEpisodes([]); setSmartEpisodesRange(""); }}
                        style={{fontSize:"0.75rem", color:"var(--text-muted)", background:"none", border:"none", cursor:"pointer"}}
                      >✕ Otkaži</button>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>
          );
        })()}

        {activeTab === "voyo" && (
          <div key="voyo" className="tab-content">
            <div className="tab-page-header tab-header-voyo mb-8">
              <div className="tab-page-header-icon" style={{background:"linear-gradient(135deg,#f97316,#ea580c)"}}>
                <Tv style={{width:24,height:24,color:"white"}} />
              </div>
              <div>
                <h2 className="text-2xl font-extrabold text-white mb-1 flex items-center gap-2.5">
                  <Tv className="w-6 h-6 text-orange-500" /> Voyo RS
                </h2>
                <p className="text-text-secondary text-sm">Preuzmite filmove, epizode i cele serije sa Voyo.rs platforme uz Widevine dekripciju. Podržava automatsko preuzimanje titlova i spajanje.</p>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
              
              {/* Downloader Form */}
              <div className="md:col-span-2 glass-panel p-8 rounded-xl border border-glass flex flex-col gap-6">
                <div>
                  <label>Izaberite tip preuzimanja</label>
                  <div className="sliding-tabs-wrapper">
                    <div
                      className="sliding-tabs-slider"
                      style={{
                        width: "calc(50% - 4px)",
                        transform: `translateX(${voyoMode === "video" ? "0%" : "100%"})`
                      }}
                    />
                    <button
                      type="button"
                      onClick={() => { setVoyoMode("video"); setVoyoSeriesData(null); setVoyoEpisodesRange(""); }}
                      className={`sliding-tabs-btn ${voyoMode === "video" ? "active" : ""}`}
                    >
                      <Film className="w-4 h-4" /> Film / Epizoda
                    </button>
                    {/* Bug 7 Fix: also reset voyoEpisodesRange when switching to series */}
                    <button
                      type="button"
                      onClick={() => { setVoyoMode("series"); setVoyoEpisodesRange(""); }}
                      className={`sliding-tabs-btn ${voyoMode === "series" ? "active" : ""}`}
                    >
                      <List className="w-4 h-4" /> Cela Serija
                    </button>
                  </div>
                </div>

                <div>
                  <label>{voyoMode === "video" ? "URL ili ID videa" : "ID serije"}</label>
                  <div className="flex gap-2">
                    <input
                      type="text"
                      placeholder={voyoMode === "video" ? "npr. https://voyo.rs/uspeh-1_50584.html ili ID 50584" : "npr. 542"}
                      value={voyoTarget}
                      onChange={(e) => setVoyoTarget(e.target.value)}
                      onKeyDown={(e) => e.key === "Enter" && voyoMode === "series" && searchVoyoSeries()}
                    />
                    {voyoMode === "series" && (
                      <button
                        onClick={searchVoyoSeries}
                        disabled={voyoSearching || !voyoTarget}
                        className="btn btn-secondary"
                      >
                        {voyoSearching ? <Loader2 className="w-4 h-4 animate-spin" /> : <Search className="w-4 h-4" />}
                        Pretraži
                      </button>
                    )}
                  </div>
                </div>

                <div>
                  <label>Kvalitet preuzimanja (Resolution)</label>
                  <CustomSelect
                    value={voyoRes}
                    options={["1080p", "720p", "480p"]}
                    onChange={(val) => setVoyoRes(val)}
                    formatLabel={(val) => val === "1080p" ? "1080p (Full HD - podrazumevano)" : val === "720p" ? "720p (HD)" : "480p (SD)"}
                  />
                </div>

                {/* Series Details & Episode Checklist */}
                {voyoMode === "series" && voyoSeriesData && (
                  <div className="border-t border-glass pt-6 flex flex-col gap-4">
                    <div>
                      <h3 className="font-extrabold text-lg text-indigo-400">{voyoSeriesData.title}</h3>
                      <p className="text-xs text-text-secondary mt-1">{voyoSeriesData.description}</p>
                    </div>

                    <div>
                      <div className="flex justify-between items-center mb-2">
                        <label className="m-0">Epizode u seriji ({voyoSeriesData.episodes.length})</label>
                        <div className="flex gap-2">
                          <button
                            className="text-xs text-indigo-400 font-bold hover:underline"
                            onClick={() => setSelectedVoyoEpisodes(voyoSeriesData.episodes.map(e => e.id))}
                          >
                            Označi sve
                          </button>
                          <span className="text-text-muted">|</span>
                          <button
                            className="text-xs text-indigo-400 font-bold hover:underline"
                            onClick={() => setSelectedVoyoEpisodes([])}
                          >
                            Odznači sve
                          </button>
                        </div>
                      </div>

                      <div className="max-h-60 overflow-y-auto border border-glass rounded-lg bg-black/20 p-2 flex flex-col gap-1">
                        {voyoSeriesData.episodes.map((ep) => {
                          const checked = selectedVoyoEpisodes.includes(ep.id);
                          return (
                            <label key={ep.id} className="custom-checkbox-wrap" style={{borderRadius:8,padding:"8px 10px"}} onClick={() => {
                              if (checked) setSelectedVoyoEpisodes(selectedVoyoEpisodes.filter(id => id !== ep.id));
                              else setSelectedVoyoEpisodes([...selectedVoyoEpisodes, ep.id]);
                            }}>
                              <div className={`custom-checkbox-box ${checked ? "checked" : ""}`}>
                                <svg className="custom-checkbox-check" viewBox="0 0 10 10" fill="none" stroke="white" strokeWidth="2">
                                  <polyline points="1.5 5 4 7.5 8.5 2" />
                                </svg>
                              </div>
                              <span className="font-bold text-indigo-300 min-w-16">S{ep.season.toString().padStart(2, "0")}E{ep.episode.toString().padStart(2, "0")}</span>
                              <span className="flex-1 truncate text-white text-sm">{ep.title}</span>
                              <span className="text-xs text-text-muted">{ep.length_mins}m</span>
                              {ep.drm && <span title="DRM Zaštićeno"><Lock className="w-3.5 h-3.5 text-amber-500" /></span>}
                              {ep.has_subs && <span title="Titlovi dostupni"><FileText className="w-3.5 h-3.5 text-indigo-400" /></span>}
                            </label>
                          );
                        })}
                      </div>
                    </div>

                    {/* F4: Clarify range vs checkbox priority */}
                    <div>
                      <label>Raspon epizoda (opciono)</label>
                      <input
                        type="text"
                        placeholder="npr. 1-3, 5-, -4"
                        value={voyoEpisodesRange}
                        onChange={(e) => setVoyoEpisodesRange(e.target.value)}
                      />
                      <p className="text-[11px] text-amber-400 mt-1.5 flex items-center gap-1">
                        <Info className="w-3 h-3 flex-shrink-0" />
                        {voyoEpisodesRange
                          ? "⚡ Raspon ima prioritet — checkbox selekcija se ignoriše kada je raspon unesen."
                          : "Ostavi prazno da koristiš epizode označene checkboxom gore."}
                      </p>
                    </div>
                  </div>
                )}

                <button
                  onClick={startVoyoDownload}
                  disabled={!voyoTarget}
                  className="btn btn-primary w-full py-4 text-base"
                >
                  <Download className="w-5 h-5" />
                  Započni Preuzimanje
                </button>
              </div>

              {/* Account / Service details */}
              <div className="flex flex-col gap-6">
                <div className="glass-panel p-6 rounded-xl border border-glass">
                  <h3 className="font-bold text-base mb-4 flex items-center gap-2">
                    <User className="w-5 h-5 text-indigo-400" />
                    Status Naloga
                  </h3>
                  
                  {status?.services.voyo.authenticated ? (
                    <div className="flex flex-col gap-3">
                      <span className="badge badge-connected">Prijavljen</span>
                      <p className="text-sm font-semibold text-white">E-mail: <span className="text-text-secondary font-normal">{status.services.voyo.email}</span></p>
                      <p className="text-sm font-semibold text-white">Profil: <span className="text-text-secondary font-normal">{status.services.voyo.nickname || "Zadano"}</span></p>
                      <p className="text-sm font-semibold text-white">Pretplata: <span className={status.services.voyo.subscribed ? "text-emerald-400 font-bold" : "text-red-400 font-bold"}>{status.services.voyo.subscribed ? "Aktivna ✓" : "Nije aktivna ✗"}</span></p>
                    </div>
                  ) : (
                    <div className="flex flex-col gap-3">
                      <span className="badge badge-missing">Nije prijavljen</span>
                      <p className="text-xs text-text-secondary">Prijavite se u "Postavkama" da biste otključali Voyo.rs preuzimanja.</p>
                    </div>
                  )}
                </div>

                {/* Voyo Tech / DRM info box */}
                <div className="glass-panel p-6 rounded-xl border border-glass flex flex-col gap-3">
                  <h4 className="font-bold text-sm flex items-center gap-2 text-orange-400">
                    <ShieldAlert className="w-4 h-4" />
                    Widevine & DRM Podrška
                  </h4>
                  <p className="text-xs text-text-secondary leading-relaxed">
                    Voyo.rs koristi AES-128 enkripciju i Widevine DRM. Naš pozadinski preuzimač automatski preuzima ključeve i vrši dekripciju bez potrebe za eksternim CDM ključevima.
                  </p>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* HRTi TAB */}
        {activeTab === "hrti" && (
          <div key="hrti" className="tab-content">
            <div className="tab-page-header tab-header-hrti mb-8">
              <div className="tab-page-header-icon" style={{background:"linear-gradient(135deg,#06b6d4,#0284c7)"}}>
                <Film style={{width:24,height:24,color:"white"}} />
              </div>
              <div>
                <h2 className="text-2xl font-extrabold text-white mb-1 flex items-center gap-2.5">
                  <Film className="w-6 h-6 text-cyan-400" /> HRTi Catalog
                </h2>
                <p className="text-text-secondary text-sm">Pregledajte, pretražujte i preuzmite filmove i serije sa HRTi streaming servisa.</p>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
              {/* Left Column — Selector & Grid */}
              <div className="md:col-span-2 flex flex-col gap-6">
                
                {/* Category selector & Search bar */}
                <div className="glass-panel p-6 rounded-xl border border-glass flex flex-col md:flex-row gap-4 justify-between items-center">
                  <div className="flex items-center gap-3 w-full md:w-auto">
                    <label className="m-0 text-xs" style={{whiteSpace:"nowrap"}}>Kategorija:</label>
                    <CustomSelect
                      value={selectedCat}
                      options={hrtiCats}
                      onChange={(val) => {
                        setSelectedCat(val);
                        fetchHrtiCategoryItems(val, 1);
                      }}
                      formatLabel={(v) => v.replace(/_/g, " ").toUpperCase()}
                      className="md-w-64"
                    />
                  </div>

                  <div className="flex gap-2 w-full md:w-96">
                    <input
                      type="text"
                      placeholder="Pretraži film ili seriju..."
                      value={hrtiSearchQuery}
                      onChange={(e) => setHrtiSearchQuery(e.target.value)}
                      onKeyDown={(e) => e.key === "Enter" && searchHrti()}
                    />
                    <button onClick={searchHrti} className="btn btn-secondary">
                      <Search className="w-4 h-4" />
                    </button>
                  </div>
                </div>

                {/* Items Grid */}
                <div className="glass-panel p-8 rounded-xl border border-glass min-h-96 relative">
                  {hrtiLoadingItems && (
                    <div className="absolute inset-0 bg-black/40 flex items-center justify-center rounded-xl">
                      <Loader2 className="w-12 h-12 text-indigo-500 animate-spin" />
                    </div>
                  )}

                  {selectedHrtiSeries ? (
                    <div className="flex justify-between items-center mb-6">
                      <div className="flex items-center gap-2">
                        <Film className="w-5 h-5 text-indigo-400" />
                        <h3 className="font-extrabold text-xl text-white">Epizode za: {selectedHrtiSeries.title}</h3>
                      </div>
                      <button
                        onClick={() => fetchHrtiCategoryItems(selectedCat, 1)}
                        className="btn btn-secondary text-xs py-2 px-4"
                      >
                        Nazad na kategoriju
                      </button>
                    </div>
                  ) : (
                    <h3 className="font-extrabold text-xl mb-6 text-white">Sadržaj na HRTi</h3>
                  )}

                  {catItems.length === 0 ? (
                    <div className="flex flex-col items-center justify-center p-20 text-center">
                      <AlertCircle className="w-12 h-12 text-text-muted mb-4" />
                      <p className="text-text-secondary font-semibold">Nema pronađenog sadržaja.</p>
                    </div>
                  ) : (
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                      {catItems.map((item) => {
                        const isMovie = item.type === "movie";
                        const cardGlow = isMovie ? "rgba(6, 182, 212, 0.25)" : "rgba(147, 51, 234, 0.25)";
                        return (
                          <div
                            key={item.id}
                            className="netflix-card group"
                            style={{ "--card-glow": cardGlow } as any}
                            onClick={() => {
                              if (item.type === "series") fetchHrtiSeriesEpisodes(item.id, item.title);
                              else startHrtiDownload(item.id, item.title);
                            }}
                          >
                            {/* Visual Thumbnail Gradient Backdrop */}
                            <div className={`absolute inset-0 w-full h-full flex items-center justify-center transition-transform duration-700 group-hover:scale-105 ${isMovie ? "hrti-thumbnail-movie" : "hrti-thumbnail-series"}`}>
                              {isMovie ? (
                                <Film className="w-16 h-16 opacity-10 text-indigo-300 transform -rotate-12 transition-transform duration-500 group-hover:scale-110 group-hover:rotate-0" />
                              ) : (
                                <Tv className="w-16 h-16 opacity-10 text-purple-300 transform rotate-12 transition-transform duration-500 group-hover:scale-110 group-hover:rotate-0" />
                              )}
                            </div>

                            {/* Floating Top-Right Badge */}
                            <div className="netflix-card-badge">
                              {isMovie ? (
                                <span className="badge flex items-center gap-1.5 bg-cyan-500/25 border-cyan-500/40 text-cyan-300 font-extrabold px-2.5 py-1 rounded-md text-[10px] tracking-wider">
                                  <Film className="w-3.5 h-3.5" /> FILM
                                </span>
                              ) : (
                                <span className="badge flex items-center gap-1.5 bg-purple-500/25 border-purple-500/40 text-purple-300 font-extrabold px-2.5 py-1 rounded-md text-[10px] tracking-wider">
                                  <Tv className="w-3.5 h-3.5" /> SERIJA
                                </span>
                              )}
                            </div>

                            {/* Center Action Play Circle */}
                            <div className="netflix-card-play">
                              {item.type === "series" ? (
                                <List className="w-5 h-5 text-indigo-900" />
                              ) : (
                                <Download className="w-5 h-5 text-cyan-900" />
                              )}
                            </div>

                            {/* Lower metadata card details */}
                            <div className="netflix-card-content">
                              <h4 className="font-extrabold text-white text-base leading-snug line-clamp-1 group-hover:text-indigo-200 transition-colors">{item.title}</h4>
                              <p className="text-[9px] text-text-muted font-mono mt-1 select-all">{item.id}</p>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  )}

                  {/* Pagination */}
                  {!selectedHrtiSeries && catTotalPages > 1 && (
                    <div className="flex justify-center items-center gap-4 mt-10">
                      <button
                        disabled={catPage <= 1}
                        onClick={() => fetchHrtiCategoryItems(selectedCat, catPage - 1)}
                        className="btn btn-secondary text-xs py-2"
                      >
                        Prethodna
                      </button>
                      <span className="text-sm font-bold text-text-secondary">Stranica {catPage} od {catTotalPages}</span>
                      <button
                        disabled={catPage >= catTotalPages}
                        onClick={() => fetchHrtiCategoryItems(selectedCat, catPage + 1)}
                        className="btn btn-secondary text-xs py-2"
                      >
                        Sledeća
                      </button>
                    </div>
                  )}
                </div>
              </div>

              {/* Right Column — Status & Details */}
              <div className="flex flex-col gap-6">
                <div className="glass-panel p-6 rounded-xl border border-glass">
                  <h3 className="font-bold text-base mb-4 flex items-center gap-2">
                    <User className="w-5 h-5 text-indigo-400" />
                    Status Naloga
                  </h3>
                  
                  {status?.services.hrti.authenticated ? (
                    <div className="flex flex-col gap-3">
                      <span className="badge badge-connected">Prijavljen</span>
                      <p className="text-sm font-semibold text-white">E-mail: <span className="text-text-secondary font-normal">{status.services.hrti.email}</span></p>
                    </div>
                  ) : (
                    <div className="flex flex-col gap-3">
                      <span className="badge badge-missing">Nije prijavljen</span>
                      <p className="text-xs text-text-secondary">Prijavite se u "Postavkama" da biste otključali HRTi preuzimanja.</p>
                    </div>
                  )}
                </div>

                <div className="glass-panel p-6 rounded-xl border border-glass flex flex-col gap-3">
                  <h4 className="font-bold text-sm flex items-center gap-2 text-cyan-400">
                    <Info className="w-4 h-4" />
                    O HRTi Katalogu
                  </h4>
                  <p className="text-xs text-text-secondary leading-relaxed">
                    HRTi katalog učitava najnovije filmove i serije direktno sa HRT platforme.
                  </p>
                  <p className="text-xs text-text-secondary leading-relaxed">
                    Preuzimanje serija podržava automatsko izlistavanje i selekciju pojedinačnih epizoda za preuzimanje.
                  </p>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* EON TAB */}
        {activeTab === "eon" && (
          <div key="eon" className="tab-content">
            <div className="tab-page-header tab-header-eon mb-8">
              <div className="tab-page-header-icon" style={{background:"linear-gradient(135deg,#10b981,#059669)"}}>
                <Play style={{width:24,height:24,color:"white"}} />
              </div>
              <div>
                <h2 className="text-2xl font-extrabold text-white mb-1 flex items-center gap-2.5">
                  <Play className="w-6 h-6 text-emerald-400" /> EON TV
                </h2>
                <p className="text-text-secondary text-sm">VOD sadržaj, serije i TV kanali uživo sa Widevine DRM dekripcijom i API katalogom.</p>
              </div>
            </div>

            {eonStatus && !eonReady && (
              <div className="mb-6 p-4 rounded-lg border border-amber-500/20 bg-amber-500/10 flex flex-col gap-2">
                <div className="flex items-center gap-2 text-amber-300 font-bold text-sm">
                  <ShieldAlert className="w-4 h-4" />
                  EON nije spreman
                </div>
                <p className="text-xs text-text-secondary">{eonStatus.error || "Proverite EON konfiguraciju."}</p>
                {eonMissing.length > 0 && (
                  <p className="text-[10px] text-text-muted font-mono">
                    Nedostaje: {eonMissing.join(", ")}
                  </p>
                )}
                {eonOptionalMissing.length > 0 && (
                  <p className="text-[10px] text-text-muted font-mono">
                    Opciono nedostaje: {eonOptionalMissing.join(", ")}
                  </p>
                )}
              </div>
            )}

            <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
              
              <div className="md:col-span-2 glass-panel p-8 rounded-xl border border-glass flex flex-col gap-6">
                <div>
                  <label>Mod Rada (EON)</label>
                  <div className="sliding-tabs-wrapper">
                    <div
                      className="sliding-tabs-slider"
                      style={{
                        width: "calc(33.333% - 4px)",
                        transform: `translateX(${eonMode === "vod" ? "0%" : eonMode === "series" ? "100%" : "200%"})`
                      }}
                    />
                    {["vod", "series", "live"].map((mode) => (
                      <button
                        key={mode}
                        type="button"
                        onClick={() => { setEonMode(mode as any); setEonTarget(""); }}
                        className={`sliding-tabs-btn ${eonMode === mode ? "active" : ""}`}
                      >
                        {mode === "vod" && "VOD / URL"}
                        {mode === "series" && "Epizode / Serije"}
                        {mode === "live" && "TV Uživo (Live)"}
                      </button>
                    ))}
                  </div>
                </div>

                {eonMode === "live" ? (
                  <div className="flex flex-col gap-3">
                    <div>
                      <label>Mod unosa TV kanala</label>
                      <div className="sliding-tabs-wrapper mb-2">
                        <div
                          className="sliding-tabs-slider"
                          style={{
                            width: "calc(50% - 4px)",
                            transform: `translateX(${eonLiveInputMode === "catalog" ? "0%" : "100%"})`
                          }}
                        />
                        <button
                          type="button"
                          onClick={() => { setEonLiveInputMode("catalog"); setEonTarget(""); }}
                          className={`sliding-tabs-btn text-xs ${eonLiveInputMode === "catalog" ? "active" : ""}`}
                        >
                          Izaberi iz liste
                        </button>
                        <button
                          type="button"
                          onClick={() => { setEonLiveInputMode("url"); setEonTarget(""); }}
                          className={`sliding-tabs-btn text-xs ${eonLiveInputMode === "url" ? "active" : ""}`}
                        >
                          Direktan live URL
                        </button>
                      </div>
                    </div>

                    {eonLiveInputMode === "catalog" ? (
                      <div>
                        <label>Izaberite TV Kanal</label>
                        <CustomSelect
                          value={eonTarget}
                          options={eonChannels}
                          onChange={(val) => setEonTarget(val)}
                          placeholder="-- Izaberi kanal iz liste --"
                          searchPlaceholder="Pretraži kanale..."
                        />
                        <p className="text-[10px] text-text-muted mt-1.5">Lista se čita iz eon_channels.json ako ga napravite u rootu aplikacije ili ~/.videodownload.</p>
                      </div>
                    ) : (
                      <div>
                        <label>Direktan Live URL (.m3u8 / .mpd)</label>
                        <input
                          type="text"
                          placeholder="npr. https://.../live/index.m3u8"
                          value={eonTarget}
                          onChange={(e) => setEonTarget(e.target.value)}
                        />
                        <p className="text-[10px] text-text-muted mt-1.5">Zalepite m3u8 manifest link iz browsera ili m3u8 strim.</p>
                      </div>
                    )}
                  </div>
                ) : (
                  <div>
                    <label>{eonMode === "vod" ? "Direktan VOD media URL" : "Series ID iz lokalnog kataloga"}</label>
                    <input
                      type="text"
                      placeholder={eonMode === "vod" ? "npr. https://.../video.m3u8 ili .mpd/.mp4" : "npr. 162073-s1"}
                      value={eonTarget}
                      onChange={(e) => setEonTarget(e.target.value)}
                    />
                    <p className="text-[10px] text-text-muted mt-1.5">
                      {eonMode === "vod"
                        ? "Unesite EON VOD ID (npr. sa linka /ondemand/detail/12345), manifest URL ili direktan video link."
                        : "Epizode se čitaju iz EON API-ja ili lokalnog eon_series.json fajla."}
                    </p>
                  </div>
                )}

                {eonMode === "live" && (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                      {/* F5: Default 3600s (1h) */}
                      <label>Trajanje snimanja (sekunde)</label>
                      <input
                        type="number"
                        value={eonDuration}
                        onChange={(e) => setEonDuration(parseInt(e.target.value) || 0)}
                      />
                      <p className="text-[10px] text-text-muted mt-1">
                        * 0 = snimaj bez prestanka &nbsp;|&nbsp; 3600 = 1 sat &nbsp;|&nbsp; 7200 = 2 sata
                      </p>
                    </div>

                    <div className="flex flex-col justify-end">
                      <label className="flex items-center gap-3 p-3 rounded border border-glass cursor-pointer select-none">
                        <input
                          type="checkbox"
                          className="w-4 h-4 cursor-pointer"
                          checked={eonPlay}
                          onChange={(e) => setEonPlay(e.target.checked)}
                        />
                        <span className="text-sm font-semibold text-white">Gledaj tokom snimanja</span>
                      </label>
                    </div>
                  </div>
                )}

                {eonMode === "live" && eonPlay && (
                  <div>
                    <label>Putanja do video plejera (VLC/MPV - Opciono)</label>
                    <input
                      type="text"
                      placeholder="npr. C:\Program Files\VideoLAN\VLC\vlc.exe"
                      value={eonPlayerPath}
                      onChange={(e) => setEonPlayerPath(e.target.value)}
                    />
                  </div>
                )}

                {eonMode === "series" && (
                  <div>
                    <label>Raspon Epizoda</label>
                    <input
                      type="text"
                      placeholder="npr. 1-3, 2-, -5, 4 (ostavi prazno za sve epizode)"
                      value={eonEpisodesRange}
                      onChange={(e) => setEonEpisodesRange(e.target.value)}
                    />
                  </div>
                )}

                {eonMode === "vod" && (
                  <div className="border-t border-glass pt-5 flex flex-col gap-3">
                    <label>Pretraga VOD kataloga</label>
                    <div className="flex flex-col md:flex-row gap-3">
                      <input
                        type="text"
                        value={eonSearchQuery}
                        onChange={(e) => setEonSearchQuery(e.target.value)}
                        placeholder="Pretraži lokalni katalog ili API"
                        className="flex-1"
                      />
                      <button onClick={searchEonVod} className="btn btn-secondary text-xs">
                        Pretraži
                      </button>
                    </div>
                    {eonSearchResults.length > 0 && (
                      <div className="flex flex-col gap-2">
                        {eonSearchResults.slice(0, 6).map((item, idx) => {
                          const label = item.title || item.name || item.id || `Rezultat ${idx + 1}`;
                          const target = item.url || item.id || label;
                          return (
                            <button
                              key={`${label}-${idx}`}
                              onClick={() => setEonTarget(target)}
                              className="text-left p-3 rounded-lg border border-glass bg-white/[0.02] hover:bg-white/[0.05] transition"
                            >
                              <span className="block text-sm font-bold text-white">{label}</span>
                              <span className="block text-[10px] text-text-muted font-mono truncate">{target}</span>
                            </button>
                          );
                        })}
                      </div>
                    )}
                  </div>
                )}

                {eonMode === "live" && eonTarget && (
                  <div className="border-t border-glass pt-5 flex flex-col gap-3">
                    <button onClick={fetchEonEpg} className="btn btn-secondary text-xs self-start">
                      Učitaj EPG za kanal
                    </button>
                    {eonEpgItems.length > 0 && (
                      <div className="flex flex-col gap-2">
                        {eonEpgItems.slice(0, 5).map((item, idx) => (
                          <div key={idx} className="p-3 rounded-lg border border-glass bg-white/[0.02]">
                            <p className="text-sm font-bold text-white">{item.title || item.name || `Program ${idx + 1}`}</p>
                            <p className="text-[10px] text-text-muted">{item.start || ""} {item.end ? `- ${item.end}` : ""}</p>
                            {item.description && <p className="text-xs text-text-secondary mt-1">{item.description}</p>}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}

                <button
                  onClick={startEonDownload}
                  disabled={!eonTarget || !eonReady}
                  className="btn btn-primary w-full py-4"
                  title={!eonReady ? "EON engine, credentials or dependencies are missing." : undefined}
                >
                  <Download className="w-5 h-5" />
                  {eonMode === "live" ? "Započni Snimanje / Stream" : "Započni Preuzimanje"}
                </button>
              </div>

              {/* Status card */}
              <div className="flex flex-col gap-6">
                <div className="glass-panel p-6 rounded-xl border border-glass">
                  <h3 className="font-bold text-base mb-4 flex items-center gap-2">
                    <User className="w-5 h-5 text-indigo-400" />
                    Status Uređaja / Naloga
                  </h3>

                  {eonStatus?.ready ? (
                    <div className="flex flex-col gap-3">
                      <span className="badge badge-connected">Spreman</span>
                      <p className="text-sm font-semibold text-white">Nalog: <span className="text-text-secondary font-normal">{eonStatus.username}</span></p>
                      <p className="text-xs text-text-muted">Serijski broj: {eonStatus.serial}</p>
                      <p className="text-xs text-text-muted">Broj uredjaja: {eonStatus.number}</p>
                      
                      {/* EON API status details */}
                      <div className="border-t border-glass pt-3 mt-1 flex flex-col gap-1.5">
                        <span className="text-[10px] text-text-muted font-bold uppercase tracking-wider">EON API & CDM status:</span>
                        <div className="flex justify-between items-center text-xs">
                          <span className="text-text-secondary">API Konekcija:</span>
                          <span className={eonStatus.engine_status?.api?.configured ? "text-emerald-400 font-bold" : "text-amber-400 font-bold"}>
                            {eonStatus.engine_status?.api?.configured ? "Povezana ✓" : "Nije povezana"}
                          </span>
                        </div>
                        <div className="flex justify-between items-center text-xs">
                          <span className="text-text-secondary">CDM Decryption:</span>
                          <span className={eonStatus.engine_status?.cdm_ready ? "text-emerald-400 font-bold" : "text-amber-400 font-bold"}>
                            {eonStatus.engine_status?.cdm_ready ? "Učitan ✓" : "device.wvd nedostaje"}
                          </span>
                        </div>
                        {eonStatus.engine_status?.token?.expires_at && (
                          <div className="flex flex-col text-[10px] text-text-muted mt-1">
                            <span>Token ističe:</span>
                            <span className="font-mono text-white truncate">{eonStatus.engine_status.token.expires_at}</span>
                          </div>
                        )}
                      </div>
                    </div>
                  ) : (
                    <div className="flex flex-col gap-3">
                      <span className="badge badge-warning">Nije spreman</span>
                      <p className="text-xs text-text-secondary">{eonStatus?.error || "Registrujte EON nalog i proverite engine/dependencies."}</p>
                      
                      {/* EON API status details even when not fully ready */}
                      <div className="border-t border-glass pt-3 mt-1 flex flex-col gap-1.5">
                        <span className="text-[10px] text-text-muted font-bold uppercase tracking-wider">EON API & CDM status:</span>
                        <div className="flex justify-between items-center text-xs">
                          <span className="text-text-secondary">API Konekcija:</span>
                          <span className={eonStatus?.engine_status?.api?.configured ? "text-emerald-400 font-bold" : "text-red-400 font-bold"}>
                            {eonStatus?.engine_status?.api?.configured ? "Povezana ✓" : "Nije povezana"}
                          </span>
                        </div>
                        <div className="flex justify-between items-center text-xs">
                          <span className="text-text-secondary">CDM Decryption:</span>
                          <span className={eonStatus?.engine_status?.cdm_ready ? "text-emerald-400 font-bold" : "text-red-400 font-bold"}>
                            {eonStatus?.engine_status?.cdm_ready ? "Učitan ✓" : "device.wvd nedostaje"}
                          </span>
                        </div>
                      </div>

                      {eonMissing.length > 0 && (
                        <p className="text-[10px] text-text-muted font-mono break-all">Missing: {eonMissing.join(", ")}</p>
                      )}
                      {eonOptionalMissing.length > 0 && (
                        <p className="text-[10px] text-text-muted font-mono break-all">Optional: {eonOptionalMissing.join(", ")}</p>
                      )}
                    </div>
                  )}
                </div>

                <div className="glass-panel p-6 rounded-xl border border-glass flex flex-col gap-4">
                  <h3 className="font-bold text-base flex items-center gap-2">
                    <Lock className="w-5 h-5 text-indigo-400" />
                    EON podaci
                  </h3>
                  <div>
                    <label>Korisničko ime / email</label>
                    <input
                      type="text"
                      value={eonUsername}
                      onChange={(e) => setEonUsername(e.target.value)}
                      placeholder="sbb_user@email.com"
                    />
                  </div>
                  <div>
                    <label>Lozinka</label>
                    <input
                      type="password"
                      value={eonPassword}
                      onChange={(e) => setEonPassword(e.target.value)}
                      placeholder="••••••••"
                    />
                  </div>
                  <div className="grid grid-cols-1 gap-3">
                    <div>
                      <label>Device serial</label>
                      <input
                        type="text"
                        value={eonSerial}
                        onChange={(e) => setEonSerial(e.target.value)}
                        placeholder="device-serial"
                      />
                    </div>
                    <div>
                      <label>Device number</label>
                      <input
                        type="text"
                        value={eonNumber}
                        onChange={(e) => setEonNumber(e.target.value)}
                        placeholder="device-number"
                      />
                    </div>
                  </div>
                  <button
                    onClick={() => submitLogin("eon", { username: eonUsername, password: eonPassword, serial: eonSerial, number: eonNumber })}
                    disabled={!eonUsername || !eonPassword || !eonSerial || !eonNumber}
                    className="btn btn-secondary text-xs"
                  >
                    Sačuvaj EON podatke
                  </button>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    <button
                      onClick={loginEonApi}
                      disabled={!eonUsername || !eonPassword || !eonSerial || !eonNumber}
                      className="btn btn-secondary text-xs"
                    >
                      API login token
                    </button>
                    <button
                      onClick={refreshEonApiToken}
                      className="btn btn-secondary text-xs"
                    >
                      Osveži API token
                    </button>
                  </div>
                  <p className="text-[10px] text-text-muted">
                    Ova dugmad koriste samo vaš lokalni eon_api.json šablon. Ako API nije popunjen, možete i dalje koristiti lokalne kataloge i direktne media URL-ove.
                  </p>
                </div>

                <div className="glass-panel p-6 rounded-xl border border-glass flex flex-col gap-4">
                  <h3 className="font-bold text-base flex items-center gap-2">
                    <FileText className="w-5 h-5 text-indigo-400" />
                    Lokalne datoteke
                  </h3>
                  <div className="flex flex-col gap-2">
                    <span className={`badge ${deviceWvdInfo?.found ? "badge-connected" : "badge-missing"}`}>
                      {deviceWvdInfo?.found ? "device.wvd pronađen" : "device.wvd nije podešen"}
                    </span>
                    <input
                      type="text"
                      value={binariesPaths.device_wvd || ""}
                      onChange={(e) => setBinariesPaths({ ...binariesPaths, device_wvd: e.target.value })}
                      placeholder="D:\ProjektiApp\videodownloadservisi\device.wvd"
                      className="font-mono text-xs"
                    />
                    <button onClick={handleSaveDeviceWvdPath} className="btn btn-secondary text-xs">
                      Sačuvaj device.wvd
                    </button>
                  </div>
                  <div className="border-t border-glass pt-4 text-[10px] text-text-muted font-mono break-all">
                    Katalog kanala: {eonCatalogPath("eon_channels.json")}
                    <br />
                    Katalog serija: {eonCatalogPath("eon_series.json")}
                    <br />
                    API šablon: {eonCatalogPath("eon_api.json")}
                  </div>
                  <button onClick={initEonCatalogs} className="btn btn-secondary text-xs">
                    Napravi početne katalog fajlove
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* RTS PLANETA TAB */}
        {activeTab === "rts" && (
          <div key="rts" className="tab-content">
            <div className="tab-page-header tab-header-rts mb-8">
              <div className="tab-page-header-icon" style={{background:"linear-gradient(135deg,#f43f5e,#e11d48)"}}>
                <Radio style={{width:24,height:24,color:"white"}} />
              </div>
              <div>
                <h2 className="text-2xl font-extrabold text-white mb-1 flex items-center gap-2.5">
                  <Radio className="w-6 h-6 text-rose-500" /> RTS Planeta
                </h2>
                <p className="text-text-secondary text-sm">Preuzmite filmove i epizode serija sa RTS Planeta platforme. Podržava Widevine L3 dekripciju.</p>
                <p className="text-xs text-text-muted mt-1">Primeri linkova: <code className="font-mono text-rose-400 bg-white/[0.04] px-1 rounded">rtsplaneta.rs/sr_lat/serial/...</code> ili <code className="font-mono text-rose-400 bg-white/[0.04] px-1 rounded">.../film/...</code></p>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
              
              <div className="md:col-span-2 glass-panel p-8 rounded-xl border border-glass flex flex-col gap-6">
                <div>
                  <label>URL Sadržaja sa RTS Planete</label>
                  <input
                    type="text"
                    placeholder="npr. https://rtsplaneta.rs/sr_lat/serial/4276399/ranjeni-orao"
                    value={rtsTarget}
                    onChange={(e) => setRtsTarget(e.target.value)}
                  />
                  <p className="text-[10px] text-text-muted mt-1.5">Unesite link ka epizodi ili glavnoj seriji.</p>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label>Početna Epizoda (opciono)</label>
                    <input
                      type="number"
                      placeholder="npr. 1"
                      value={rtsStartEp}
                      onChange={(e) => setRtsStartEp(e.target.value)}
                    />
                  </div>
                  <div>
                    <label>Krajnja Epizoda (opciono)</label>
                    <input
                      type="number"
                      placeholder="npr. 5"
                      value={rtsEndEp}
                      onChange={(e) => setRtsEndEp(e.target.value)}
                    />
                  </div>
                </div>

                <label className="flex items-center gap-3 p-3 rounded border border-glass cursor-pointer select-none">
                  <input
                    type="checkbox"
                    className="w-4 h-4 cursor-pointer"
                    checked={rtsVerbose}
                    onChange={(e) => setRtsVerbose(e.target.checked)}
                  />
                  <span className="text-sm font-semibold text-white">Prikaži debug logove (Verbose)</span>
                </label>

                <button
                  onClick={startRtsDownload}
                  disabled={!rtsTarget}
                  className="btn btn-primary w-full py-4"
                >
                  <Download className="w-5 h-5" />
                  Započni Preuzimanje
                </button>
              </div>

              {/* Status details */}
              <div className="flex flex-col gap-6">
                <div className="glass-panel p-6 rounded-xl border border-glass">
                  <h3 className="font-bold text-base mb-4 flex items-center gap-2">
                    <User className="w-5 h-5 text-indigo-400" />
                    Kredencijali
                  </h3>
                  
                  {status?.services.rtsplaneta.authenticated ? (
                    <div className="flex flex-col gap-3">
                      <span className="badge badge-connected">Povezano</span>
                      <p className="text-sm text-text-secondary">E-mail nalog je registrovan i spreman.</p>
                    </div>
                  ) : (
                    <div className="flex flex-col gap-3">
                      <span className="badge badge-warning">Nedostaju</span>
                      <p className="text-xs text-text-secondary">Sačuvajte vaše RTS kredencijale u "Postavkama".</p>
                    </div>
                  )}
                </div>

                {/* CDM alert */}
                <div className="glass-panel p-6 rounded-xl border border-glass flex flex-col gap-3">
                  <h4 className="font-bold text-sm flex items-center gap-2 text-amber-500">
                    <ShieldAlert className="w-4 h-4" />
                    Widevine L3 Potreban
                  </h4>
                  <p className="text-xs text-text-secondary">
                    RTS Planeta koristi Widevine enkripciju. Proverite da li imate sačuvan <code className="font-mono text-indigo-400 bg-white/[0.04] px-1 py-0.5 rounded">device.wvd</code> fajl u folderu binaries ili rootu aplikacije.
                  </p>
                </div>

                {/* RTS Tutorial Box */}
                <div className="glass-panel p-6 rounded-xl border border-glass flex flex-col gap-3">
                  <h4 className="font-bold text-sm flex items-center gap-2 text-indigo-400">
                    <Info className="w-4 h-4" />
                    Kako preuzeti sa RTS-a:
                  </h4>
                  <ol className="text-xs text-text-secondary list-decimal pl-4 flex flex-col gap-2">
                    <li>Prijavite se na sajt <a href="https://rtsplaneta.rs" target="_blank" rel="noreferrer" className="text-indigo-400 hover:underline">rtsplaneta.rs</a>.</li>
                    <li>Kopirajte URL adresu filma ili serije.</li>
                    <li>Nalepite link u polje sa leve strane.</li>
                    <li>Unesite raspon epizoda po potrebi.</li>
                    <li>Kliknite "Započni Preuzimanje" za preuzimanje epizoda.</li>
                  </ol>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* HBO MAX TAB */}
        {activeTab === "hbo" && (
          <div key="hbo" className="tab-content">
            <div className="tab-page-header tab-header-hbo mb-6">
              <div className="tab-page-header-icon" style={{background:"linear-gradient(135deg,#9333ea,#7e22ce)"}}>
                <Clapperboard style={{width:24,height:24,color:"white"}} />
              </div>
              <div>
                <h2 className="text-2xl font-extrabold text-white mb-1 flex items-center gap-2.5">
                  <Clapperboard className="w-6 h-6 text-purple-400" /> HBO Max
                </h2>
                <p className="text-text-secondary text-sm">Prijava uređaja, preuzimanje po Video ID-u, ili Bypass Mode sa direktnim MPD/License URL-ovima.</p>
              </div>
            </div>

            {/* Mode Toggle */}
            <div className="sliding-tabs-wrapper mb-6">
              <div
                className="sliding-tabs-slider"
                style={{
                  width: "calc(50% - 4px)",
                  transform: `translateX(${!hboDirectMode ? "0%" : "100%"})`
                }}
              />
              <button
                type="button"
                onClick={() => setHboDirectMode(false)}
                className={`sliding-tabs-btn ${!hboDirectMode ? "active" : ""}`}
              >
                Standardno (Login + ID)
              </button>
              <button
                type="button"
                onClick={() => setHboDirectMode(true)}
                className={`sliding-tabs-btn ${hboDirectMode ? "active" : ""}`}
              >
                ⚡ Bypass Mode (Direct URL)
              </button>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
              
              <div className="md:col-span-2 flex flex-col gap-6">

                {!hboDirectMode ? (
                  <>
                    {/* Login trigger card */}
                    <div className="glass-panel p-8 rounded-xl border border-glass flex flex-col gap-6">
                      <h3 className="font-extrabold text-lg text-white">Prijava (Login)</h3>
                      <p className="text-xs text-text-secondary">
                        HBO koristi autentifikaciju preko koda. Klikom na dugme pokrećete sesiju u pozadini koja će izgenerisati kod za prijavu. Detaljan kod i link ćete videti otvaranjem <strong>Logs</strong> dugmeta na kartici prijave u redu preuzimanja!
                      </p>
                      
                      <div className="flex gap-4 items-end">
                        <div className="flex-1">
                          <label>Region / Tržište (Market)</label>
                          <CustomSelect
                            value={hboMarket}
                            options={["emea", "us"]}
                            onChange={(val) => setHboMarket(val)}
                            formatLabel={(val) => val === "emea" ? "EMEA (Evropa - podrazumevano)" : "US (Amerika)"}
                          />
                        </div>
                        
                        <button
                          onClick={startHboLogin}
                          className="btn btn-secondary btn-align-select px-6"
                        >
                          Pokreni Prijavu
                        </button>
                      </div>
                    </div>

                    {/* Standard Downloader Form */}
                    <div className="glass-panel p-8 rounded-xl border border-glass flex flex-col gap-6">
                      <h3 className="font-extrabold text-lg text-white">Preuzimanje Videa (po ID-u)</h3>
                      
                      <div>
                        <label>Video ID (Zadnji deo URL-a)</label>
                        <input
                          type="text"
                          placeholder="npr. de4c9160-1b67-4c1e-8cad-e7b0e42c5fdf"
                          value={hboTarget}
                          onChange={(e) => setHboTarget(e.target.value)}
                        />
                        <p className="text-[10px] text-text-muted mt-1.5">
                          URL na HBO Max izgleda ovako: <code className="font-mono bg-white/[0.04] px-1 py-0.5 rounded text-indigo-400">.../watch/&lt;id1&gt;/&lt;id2&gt;</code>. Kopirajte samo <code className="font-mono text-indigo-400 font-bold">&lt;id2&gt;</code> (zadnji UUID).
                        </p>
                      </div>

                      <div>
                        <label>Jezici za titlove (odvojeni zarezom)</label>
                        <input
                          type="text"
                          placeholder="npr. sr,hr,mk,bs,sl ili 'none' za bez titlova"
                          value={hboSubs}
                          onChange={(e) => setHboSubs(e.target.value)}
                        />
                      </div>

                      <button
                        onClick={startHboDownload}
                        disabled={!hboTarget}
                        className="btn btn-primary w-full py-4"
                      >
                        <Download className="w-5 h-5" />
                        Započni Preuzimanje
                      </button>
                    </div>
                  </>
                ) : (
                  /* ─── BYPASS / DIRECT MODE ─── */
                  <div className="glass-panel p-8 rounded-xl border border-indigo-500/40 flex flex-col gap-6" style={{background: "linear-gradient(135deg, rgba(99,102,241,0.08) 0%, rgba(139,92,246,0.06) 100%)"}}>
                    <div className="flex items-center gap-3 mb-2">
                      <span className="text-2xl">⚡</span>
                      <div>
                        <h3 className="font-extrabold text-lg text-white">Bypass Mode — Direktni URL-ovi</h3>
                        <p className="text-xs text-indigo-300 mt-0.5">Zaobiđite login! Zalepite MPD Manifest i Widevine License URL iz DevTools-a ili browser-a.</p>
                      </div>
                    </div>

                    <div className="p-4 rounded-lg bg-amber-500/10 border border-amber-500/30 text-xs text-amber-200 flex gap-2">
                      <span className="text-base">💡</span>
                      <div>
                        <strong>Kako do URL-ova?</strong> Otvorite DevTools (F12) → Network tab → pokrenite video na max.com → filtrirajte po <code className="font-mono bg-white/10 px-1 rounded">.mpd</code> za Manifest, i po <code className="font-mono bg-white/10 px-1 rounded">widevine</code> ili <code className="font-mono bg-white/10 px-1 rounded">license</code> za License URL.
                      </div>
                    </div>

                    <div>
                      <label>📄 Manifest URL (.mpd)</label>
                      <input
                        type="url"
                        placeholder="https://...cdn.max.com/.../.mpd?..."
                        value={hboManifestUrl}
                        onChange={(e) => setHboManifestUrl(e.target.value)}
                        className={hboManifestUrl && !hboManifestUrl.includes('mpd') ? 'border-amber-500/50' : ''}
                      />
                      {hboManifestUrl && !hboManifestUrl.toLowerCase().includes('mpd') && (
                        <p className="text-[10px] text-amber-400 mt-1">⚠ URL ne izgleda kao .mpd manifest – proverite URL</p>
                      )}
                    </div>

                    <div>
                      <label>🔑 License URL (Widevine)</label>
                      <input
                        type="url"
                        placeholder="https://widevine.any-any.prd.max.com/widevine/v1/license"
                        value={hboLicenseUrl}
                        onChange={(e) => setHboLicenseUrl(e.target.value)}
                      />
                    </div>

                    <div>
                      <label>📝 Naslov (opciono)</label>
                      <input
                        type="text"
                        placeholder="npr. Ime filma ili serije (ostavite prazno za auto)"
                        value={hboDirectTitle}
                        onChange={(e) => setHboDirectTitle(e.target.value)}
                      />
                    </div>

                    <div>
                      <label>Jezici za titlove (odvojeni zarezom)</label>
                      <input
                        type="text"
                        placeholder="npr. sr,hr,mk,bs,sl ili 'none'"
                        value={hboDirectSubs}
                        onChange={(e) => setHboDirectSubs(e.target.value)}
                      />
                    </div>

                    <button
                      onClick={startHboDirectDownload}
                      disabled={!hboManifestUrl.trim() || !hboLicenseUrl.trim()}
                      className="btn btn-primary w-full py-4"
                      style={{background: "linear-gradient(135deg, #6366f1, #8b5cf6)"}}
                    >
                      <Download className="w-5 h-5" />
                      Pokreni Bypass Preuzimanje
                    </button>
                  </div>
                )}
              </div>

              {/* Account / status details */}
              <div className="flex flex-col gap-6">
                <div className="glass-panel p-6 rounded-xl border border-glass">
                  <h3 className="font-bold text-base mb-4 flex items-center gap-2">
                    <User className="w-5 h-5 text-indigo-400" />
                    Autentifikacija
                  </h3>
                  
                  {status?.services.hbomax.authenticated ? (
                    <div className="flex flex-col gap-3">
                      <span className="badge badge-connected">Prijavljen ✓</span>
                      <p className="text-xs text-text-secondary">Token je prisutan na sistemu. HBO downloads bi trebalo da rade normalno.</p>
                    </div>
                  ) : (
                    <div className="flex flex-col gap-3">
                      <span className="badge badge-warning">Nema tokena</span>
                      <p className="text-xs text-text-secondary">Pokrenite proces prijave sa leve strane da kreirate HBO Max token.</p>
                    </div>
                  )}

                  {/* Show active market */}
                  <div className="mt-4 pt-4 border-t border-glass flex items-center gap-2">
                    <Globe className="w-4 h-4 text-text-muted" />
                    <span className="text-xs text-text-secondary">Market: <span className="font-bold text-white uppercase">{hboMarket}</span></span>
                  </div>
                </div>

                {/* Direct mode info card */}
                {hboDirectMode && (
                  <div className="glass-panel p-6 rounded-xl border border-indigo-500/30">
                    <h3 className="font-bold text-base mb-3 flex items-center gap-2">
                      <span className="text-indigo-400">⚡</span>
                      Bypass Mode Info
                    </h3>
                    <ul className="text-xs text-text-secondary space-y-2">
                      <li>✅ <strong className="text-white">Ne treba login</strong> – direktno koristite URL-ove</li>
                      <li>✅ Radi <strong className="text-white">bez tokena</strong> u lokalnom keju</li>
                      <li>⚠ URL-ovi <strong className="text-amber-300">isteknu brzo</strong> – koristite odmah!</li>
                      <li>🔑 Potreban je CDM (.wvd) za dekripciju</li>
                    </ul>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {/* SETTINGS TAB */}
        {activeTab === "settings" && (
          <div key="settings" className="tab-content">
            <div className="tab-page-header tab-header-settings mb-8">
              <div className="tab-page-header-icon" style={{background:"linear-gradient(135deg,#6366f1,#4f46e5)"}}>
                <Settings style={{width:24,height:24,color:"white"}} />
              </div>
              <div>
                <h2 className="text-2xl font-extrabold text-white mb-1 flex items-center gap-2.5">
                  <Settings className="w-6 h-6 text-indigo-400" /> Postavke Aplikacije
                </h2>
                <p className="text-text-secondary text-sm">Podesite kredencijale za servise, izlazni direktorijum i putanje do eksternih alata.</p>
              </div>
            </div>

            <div className="flex flex-col gap-8">

              {/* F3: Services Authentication Status Overview */}
              {status && (
                <div className="glass-panel p-6 rounded-xl border border-glass">
                  <h3 className="font-bold text-base mb-4 flex items-center gap-2">
                    <Server className="w-4 h-4 text-indigo-400" />
                    Pregled Autentifikacije Servisa
                  </h3>
                  <div className="service-status-grid">
                    {[
                      { key: "voyo",       label: "Voyo RS",     icon: Tv,     color: "service-voyo" },
                      { key: "hrti",       label: "HRTi",        icon: Film,   color: "service-hrti" },
                      { key: "eon",        label: "EON TV",      icon: Play,   color: "service-eon"  },
                      { key: "rtsplaneta", label: "RTS Planeta", icon: Radio,  color: "service-rts"  },
                      { key: "hbomax",     label: "HBO Max",     icon: Zap,    color: "service-hbo"  },
                    ].map(({ key, label, icon: Icon, color }) => {
                      const serviceStatus = status.services[key];
                      const auth = key === "eon" ? Boolean(serviceStatus?.ready) : Boolean(serviceStatus?.authenticated);
                      return (
                        <div key={key} className={`service-status-card ${auth ? "authenticated" : "not-authenticated"}`}>
                          <Icon className={`w-5 h-5 ${color}`} />
                          <span className="text-xs font-bold text-white">{label}</span>
                          <span className={`text-[10px] font-semibold ${auth ? "text-emerald-400" : "text-red-400"}`}>
                            {auth ? "Spreman" : "Nije spreman"}
                          </span>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* Folder and Binaries Status */}
              <div className="glass-panel p-8 rounded-xl border border-glass flex flex-col gap-6">
                <h3 className="font-extrabold text-xl text-indigo-400 flex items-center gap-2">
                  <Settings className="w-5 h-5" />
                  Sistemska Podešavanja
                </h3>

                <div>
                  <label>Izlazni folder za preuzete filmove/serije (Output Directory)</label>
                  <input
                    type="text"
                    value={outputDir}
                    onChange={(e) => setOutputDir(e.target.value)}
                    className="input-premium"
                  />
                  <p className="text-[10px] text-text-muted mt-1.5">* Svi preuzeti MKV video fajlovi biće sačuvani na ovoj lokaciji.</p>
                </div>

                <div className="border-t border-glass pt-6">
                  <h4 className="font-bold text-sm text-white mb-4">Detektovani Eksterni Alati & CDM</h4>
                  
                  <div className="exec-monitor-grid">
                    {status && Object.entries(status.binaries).map(([name, info]) => (
                      <BinaryPathCard
                        key={name}
                        name={name}
                        found={info.found}
                        pathValue={binariesPaths[name] || ""}
                        onChange={(val) => setBinariesPaths({ ...binariesPaths, [name]: val })}
                        showToast={showToast}
                      />
                    ))}
                  </div>
                </div>

                <button
                  onClick={handleSaveConfig}
                  disabled={saveFeedback}
                  className={`btn self-end transition-all ${saveFeedback ? "bg-emerald-600 text-white border border-emerald-500 shadow-emerald" : "btn-primary"}`}
                >
                  {saveFeedback ? (
                    <span className="flex items-center gap-2">
                      <Check className="w-4 h-4" />
                      Podešavanja sačuvana!
                    </span>
                  ) : (
                    "Sačuvaj Podešavanja"
                  )}
                </button>
              </div>

              {/* Session / Cookie Import Panel to bypass CAPTCHA */}
              <div className="glass-panel p-8 rounded-xl border border-glass flex flex-col gap-6">
                <h3 className="font-extrabold text-xl text-amber-400 flex items-center gap-2">
                  <ShieldAlert className="w-5 h-5 text-amber-400" />
                  Uvoz Sesije / Kolačića (Bypass CAPTCHA)
                </h3>
                <p className="text-sm text-text-secondary leading-relaxed m-0">
                  Ukoliko neki od servisa (RTS, Voyo, HRTi, HBO) zahteva CAPTCHA zaštitu ili verifikaciju na formi za logovanje,
                  možete se ulogovati normalno u vašem brauzeru, kopirati token ili sesiju (npr. preko EditThisCookie ekstenzije) i uvesti ga ovde.
                </p>

                {importService === "hbomax" && (
                  <div className="bg-amber-500/10 border border-amber-500/30 rounded-lg p-6 flex flex-col gap-3">
                    <div className="font-extrabold text-amber-400 flex items-center gap-2 text-sm">
                      <Sparkles className="w-4 h-4 text-amber-400 animate-pulse" />
                      Najbrži način za HBO Max (Magično kopiranje u 1 sekundi)
                    </div>
                    <p className="text-xs text-text-secondary leading-relaxed m-0">
                      Najnovije verzije pretraživača (Google Chrome, Edge) imaju novu naprednu zaštitu (v20 Application-Bound Encryption) koja blokira spoljne programe da direktno čitaju njihove fajlove.
                      Zato smo napravili <strong>magičnu skriptu od jedne sekunde</strong> koja sama pronalazi i kopira Vaš token!
                    </p>
                    <ol className="list-decimal pl-5 flex flex-col gap-1.5 text-xs text-text-secondary m-0">
                      <li>Otvorite tab u pretraživaču gde gledate <strong>Max</strong> (ili hbomax.com).</li>
                      <li>Pritisnite <strong>F12</strong> (ili desni klik -&gt; <em>Ispitaj / Inspect</em>) i kliknite na karticu <strong>Console</strong> (Konzola).</li>
                      <li>Nalepite liniju koda ispod i pritisnite <strong>Enter</strong>:</li>
                    </ol>
                    <div className="relative">
                      <pre className="p-3.5 bg-black/60 rounded border border-glass font-mono text-[10px] text-amber-300 overflow-x-auto select-all cursor-pointer m-0">
                        {`copy(JSON.stringify(JSON.parse(localStorage.getItem('token') || '{}'), null, 2)); console.log('Uspelo! HBO Max podaci su kopirani u clipboard!');`}
                      </pre>
                    </div>
                  </div>
                )}

                <div className="flex flex-col gap-4">
                  <div>
                    <label>Izaberite servis</label>
                    <CustomSelect
                      value={importService}
                      options={["voyo", "hrti", "rtsplaneta", "hbomax"]}
                      onChange={(val) => setImportService(val)}
                      formatLabel={(val) => {
                        if (val === "voyo") return "Voyo RS";
                        if (val === "hrti") return "HRTi";
                        if (val === "rtsplaneta") return "RTS Planeta";
                        if (val === "hbomax") return "HBO Max";
                        return val;
                      }}
                      className="max-w-xs"
                    />
                  </div>

                  <div>
                    <label>Podaci o sesiji (Token / Cookie JSON string)</label>
                    <textarea
                      placeholder="Nalepite kopirani token ili sesijski JSON ovde..."
                      onChange={(e) => setImportSessionData(e.target.value)}
                      rows={5}
                      className="py-2.5 px-3 bg-black/40 border border-glass text-white rounded focus:outline-none w-full font-mono text-xs"
                    />
                  </div>

                  <button
                    onClick={handleImportSession}
                    disabled={importLoading || !importSessionData.trim()}
                    className="btn btn-primary self-end gap-2"
                  >
                    {importLoading ? (
                      <Loader2 className="w-5 h-5 animate-spin" />
                    ) : (
                      <Download className="w-5 h-5" />
                    )}
                    Uvezi Sesiju
                  </button>
                </div>
              </div>
              <div className="glass-panel p-8 rounded-xl border border-glass flex flex-col gap-6">
                <h3 className="font-extrabold text-xl text-indigo-400">Upravljanje Kredencijalima</h3>

                <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
                  
                  {/* Voyo Login */}
                  <div className="flex flex-col gap-4 p-6 rounded-lg bg-white/[0.02] border border-glass">
                    <h4 className="font-extrabold text-base text-white flex items-center gap-2">
                      <Tv className="w-4 h-4 service-voyo" />
                      Voyo RS prijava
                    </h4>
                    <div>
                      <label>Email</label>
                      <input type="email" value={voyoEmail} onChange={(e) => setVoyoEmail(e.target.value)} placeholder="email@voyo.rs" className="input-premium" style={{"--focused-border": "#f97316", "--focused-glow": "rgba(249,115,22,0.25)"} as any} />
                    </div>
                    <div>
                      <label>Lozinka</label>
                      <div className="password-wrapper">
                        <input
                          type={showVoyoPass ? "text" : "password"}
                          value={voyoPassword}
                          onChange={(e) => setVoyoPassword(e.target.value)}
                          placeholder="••••••••"
                          className="input-premium pr-10"
                          style={{"--focused-border": "#f97316", "--focused-glow": "rgba(249,115,22,0.25)"} as any}
                        />
                        <button
                          type="button"
                          className="password-eye-btn"
                          onClick={() => setShowVoyoPass(!showVoyoPass)}
                        >
                          {showVoyoPass ? (
                            <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" viewBox="0 0 24 24">
                              <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24" />
                              <line x1="1" y1="1" x2="23" y2="23" />
                            </svg>
                          ) : (
                            <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" viewBox="0 0 24 24">
                              <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
                              <circle cx="12" cy="12" r="3" />
                            </svg>
                          )}
                        </button>
                      </div>
                    </div>
                    <button
                      onClick={() => submitLogin("voyo", { email: voyoEmail, password: voyoPassword })}
                      className="btn btn-secondary text-xs"
                    >
                      Prijavi se na Voyo
                    </button>
                  </div>

                  {/* HRTi Credentials */}
                  <div className="flex flex-col gap-4 p-6 rounded-lg bg-white/[0.02] border border-glass">
                    <h4 className="font-extrabold text-base text-white flex items-center gap-2">
                      <Film className="w-4 h-4 service-hrti" />
                      HRTi prijava
                    </h4>
                    <div>
                      <label>Email</label>
                      <input type="email" value={hrtiEmail} onChange={(e) => setHrtiEmail(e.target.value)} placeholder="email@hrti.hr" className="input-premium" style={{"--focused-border": "#06b6d4", "--focused-glow": "rgba(6,182,212,0.25)"} as any} />
                    </div>
                    <div>
                      <label>Lozinka</label>
                      <div className="password-wrapper">
                        <input
                          type={showHrtiPass ? "text" : "password"}
                          value={hrtiPassword}
                          onChange={(e) => setHrtiPassword(e.target.value)}
                          placeholder="••••••••"
                          className="input-premium pr-10"
                          style={{"--focused-border": "#06b6d4", "--focused-glow": "rgba(6,182,212,0.25)"} as any}
                        />
                        <button
                          type="button"
                          className="password-eye-btn"
                          onClick={() => setShowHrtiPass(!showHrtiPass)}
                        >
                          {showHrtiPass ? (
                            <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" viewBox="0 0 24 24">
                              <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24" />
                              <line x1="1" y1="1" x2="23" y2="23" />
                            </svg>
                          ) : (
                            <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" viewBox="0 0 24 24">
                              <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
                              <circle cx="12" cy="12" r="3" />
                            </svg>
                          )}
                        </button>
                      </div>
                    </div>
                    <button
                      onClick={() => submitLogin("hrti", { email: hrtiEmail, password: hrtiPassword })}
                      className="btn btn-secondary text-xs"
                    >
                      Prijavi se na HRTi
                    </button>
                  </div>

                  {/* EON device credentials */}
                  <div className="flex flex-col gap-4 p-6 rounded-lg bg-white/[0.02] border border-glass lg:col-span-2">
                    <h4 className="font-extrabold text-base text-white flex items-center gap-2">
                      <Play className="w-4 h-4 service-eon" />
                      EON TV - Uređaj i Nalog
                    </h4>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <div>
                        <label>EON Korisničko Ime (Email)</label>
                        <input type="text" value={eonUsername} onChange={(e) => setEonUsername(e.target.value)} placeholder="npr. sbb_user@email.com" className="input-premium" style={{"--focused-border": "#10b981", "--focused-glow": "rgba(16,185,129,0.25)"} as any} />
                      </div>
                      <div>
                        <label>Lozinka</label>
                        <div className="password-wrapper">
                          <input
                            type={showEonPass ? "text" : "password"}
                            value={eonPassword}
                            onChange={(e) => setEonPassword(e.target.value)}
                            placeholder="••••••••"
                            className="input-premium pr-10"
                            style={{"--focused-border": "#10b981", "--focused-glow": "rgba(16,185,129,0.25)"} as any}
                          />
                          <button
                            type="button"
                            className="password-eye-btn"
                            onClick={() => setShowEonPass(!showEonPass)}
                          >
                            {showEonPass ? (
                              <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" viewBox="0 0 24 24">
                                <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24" />
                                <line x1="1" y1="1" x2="23" y2="23" />
                              </svg>
                            ) : (
                              <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" viewBox="0 0 24 24">
                                <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
                                <circle cx="12" cy="12" r="3" />
                              </svg>
                            )}
                          </button>
                        </div>
                      </div>
                      <div>
                        <label>Device Serial (Serijski Broj)</label>
                        <input type="text" value={eonSerial} onChange={(e) => setEonSerial(e.target.value)} placeholder="kopiraj iz payload-a" className="input-premium" style={{"--focused-border": "#10b981", "--focused-glow": "rgba(16,185,129,0.25)"} as any} />
                        <p className="text-[10px] text-text-muted mt-1">Vrednost koju vidite kao device-serial u EON browser network payload-u.</p>
                      </div>
                      <div>
                        <label>Device Number (Broj Uređaja)</label>
                        <input type="text" value={eonNumber} onChange={(e) => setEonNumber(e.target.value)} placeholder="kopiraj iz response-a" className="input-premium" style={{"--focused-border": "#10b981", "--focused-glow": "rgba(16,185,129,0.25)"} as any} />
                        <p className="text-[10px] text-text-muted mt-1">Vrednost koju vidite kao device-number u response-u.</p>
                      </div>
                    </div>
                    <div className="border-t border-glass pt-4">
                      <label>device.wvd putanja</label>
                      <div className="flex flex-col md:flex-row gap-3">
                        <input
                          type="text"
                          value={binariesPaths.device_wvd || ""}
                          onChange={(e) => setBinariesPaths({ ...binariesPaths, device_wvd: e.target.value })}
                          placeholder="npr. D:\ProjektiApp\videodownloadservisi\device.wvd"
                          className="font-mono text-xs flex-1 input-premium"
                          style={{"--focused-border": "#10b981", "--focused-glow": "rgba(16,185,129,0.25)"} as any}
                        />
                        <button onClick={handleSaveDeviceWvdPath} className="btn btn-secondary text-xs">
                          Sacuvaj WVD
                        </button>
                      </div>
                      <p className="text-[10px] text-text-muted mt-1.5">
                        Status: {deviceWvdInfo?.found ? "pronadjen" : "nije pronadjen"} {deviceWvdInfo?.path ? `(${deviceWvdInfo.path})` : ""}
                      </p>
                    </div>
                    <button
                      onClick={() => submitLogin("eon", { username: eonUsername, password: eonPassword, serial: eonSerial, number: eonNumber })}
                      disabled={eonStatus?.engine_installed === false}
                      className="btn btn-secondary text-xs mt-2 self-start"
                      title={eonStatus?.engine_installed === false ? "Dodajte eon_downloader.py u root aplikacije." : undefined}
                    >
                      {eonStatus?.engine_installed === false ? "EON engine nedostaje" : "Sacuvaj EON uredjaj"}
                    </button>
                  </div>

                  {/* RTS Planeta */}
                  <div className="flex flex-col gap-4 p-6 rounded-lg bg-white/[0.02] border border-glass">
                    <h4 className="font-extrabold text-base text-white flex items-center gap-2">
                      <Radio className="w-4 h-4 service-rts" />
                      RTS Planeta prijava
                    </h4>
                    <div>
                      <label>Email</label>
                      <input type="email" value={rtsEmail} onChange={(e) => setRtsEmail(e.target.value)} placeholder="email@rtsplaneta.rs" className="input-premium" style={{"--focused-border": "#f43f5e", "--focused-glow": "rgba(244,63,94,0.25)"} as any} />
                    </div>
                    <div>
                      <label>Lozinka</label>
                      <div className="password-wrapper">
                        <input
                          type={showRtsPass ? "text" : "password"}
                          value={rtsPassword}
                          onChange={(e) => setRtsPassword(e.target.value)}
                          placeholder="••••••••"
                          className="input-premium pr-10"
                          style={{"--focused-border": "#f43f5e", "--focused-glow": "rgba(244,63,94,0.25)"} as any}
                        />
                        <button
                          type="button"
                          className="password-eye-btn"
                          onClick={() => setShowRtsPass(!showRtsPass)}
                        >
                          {showRtsPass ? (
                            <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" viewBox="0 0 24 24">
                              <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24" />
                              <line x1="1" y1="1" x2="23" y2="23" />
                            </svg>
                          ) : (
                            <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" viewBox="0 0 24 24">
                              <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
                              <circle cx="12" cy="12" r="3" />
                            </svg>
                          )}
                        </button>
                      </div>
                    </div>
                    <button
                      onClick={() => submitLogin("rts", { email: rtsEmail, password: rtsPassword })}
                      className="btn btn-secondary text-xs"
                    >
                      Sačuvaj RTS Kredencijale
                    </button>
                  </div>

                </div>
              </div>

            </div>
          </div>
        )}

      </main>

      {/* ── RIGHT DOCK: DOWNLOAD QUEUE ── */}
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
              {downloads.map((task) => {
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

      {/* ── TERMINAL LOGS MODAL ── */}
      {showLogModal && selectedTask && (
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
                  onClick={() => setLogFullscreen(f => !f)}
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
                selectedTask.logs.map((line, idx) => (
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
      )}

      {/* ── HRTi INLINE DOWNLOAD MODAL (replaces native prompt) ── */}
      {hrtiModal && (
        <div className="inline-modal-overlay" onClick={(e) => e.target === e.currentTarget && setHrtiModal(null)}>
          <div className="inline-modal">
            <div className="flex items-center gap-3 mb-5">
              <div style={{width:40,height:40,borderRadius:10,background:"linear-gradient(135deg,#06b6d4,#0284c7)",display:"flex",alignItems:"center",justifyContent:"center",flexShrink:0}}>
                <Download style={{width:18,height:18,color:"white"}} />
              </div>
              <div>
                <h3 className="font-extrabold text-white text-base">Preuzimanje HRTi sadržaja</h3>
                <p className="text-text-muted text-xs mt-0.5">Možete promeniti naziv fajla pre preuzimanja</p>
              </div>
            </div>
            <div className="mb-4">
              <label>Naziv fajla (opciono)</label>
              <input
                type="text"
                value={hrtiModalTitle}
                onChange={(e) => setHrtiModalTitle(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && confirmHrtiDownload()}
                placeholder={hrtiModal.title}
                autoFocus
              />
              <p className="text-[10px] text-text-muted mt-1.5">Ostavite prazno za automatski naziv: <span className="text-indigo-400 font-mono">{hrtiModal.title}</span></p>
            </div>
            <div className="flex gap-3 justify-end">
              <button
                onClick={() => { setHrtiModal(null); setHrtiModalTitle(""); }}
                className="btn btn-secondary text-sm py-2 px-5"
              >
                Otkaži
              </button>
              <button
                onClick={confirmHrtiDownload}
                className="btn btn-primary text-sm py-2 px-5"
              >
                <Download style={{width:14,height:14}} />
                Preuzmi
              </button>
            </div>
          </div>
        </div>
      )}

    </div>
  );
}
