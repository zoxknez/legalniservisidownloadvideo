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
  RefreshCw,
  Inbox,
  Radio,
  Zap,
  Globe
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

function isUrlLike(value: string): boolean {
  return /^https?:\/\//i.test(value.trim());
}

// Service metadata for sidebar
const SERVICE_META = [
  { id: "voyo",     label: "Voyo RS",      icon: Tv,       colorClass: "service-voyo" },
  { id: "hrti",     label: "HRTi Catalog", icon: Film,     colorClass: "service-hrti" },
  { id: "eon",      label: "EON TV",       icon: Play,     colorClass: "service-eon"  },
  { id: "rts",      label: "RTS Planeta",  icon: Radio,    colorClass: "service-rts"  },
  { id: "hbo",      label: "HBO Max",      icon: Zap,      colorClass: "service-hbo"  },
  { id: "settings", label: "Postavke",     icon: Settings, colorClass: "text-text-muted" },
];

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
}

function CustomSelect({ value, options, onChange, formatLabel, className = "", placeholder }: CustomSelectProps) {
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
            placeholder="Pretraži kategorije..."
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

export default function App() {
  const [activeTab, setActiveTab] = useState<string>("voyo");
  const [downloads, setDownloads] = useState<DownloadTask[]>([]);
  const [connected, setConnected] = useState<boolean>(false);
  const [status, setStatus] = useState<AppStatus | null>(null);
  
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

  // Notifications / Messages
  const [toast, setToast] = useState<{message: string; type: "success" | "error" | "info"} | null>(null);

  // F1: Confirm clear queue
  const [confirmClear, setConfirmClear] = useState<boolean>(false);

  const showToast = (message: string, type: "success" | "error" | "info" = "success") => {
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

  const startHrtiDownload = async (refId: string, itemTitle: string) => {
    try {
      const customTitle = prompt(`Unesite naziv fajla za "${itemTitle}" (ostavite prazno za podrazumevano):`, itemTitle);
      if (customTitle === null) return;
      const res = await fetch(`${getApiHost()}/api/hrti/download`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ref_id: refId, title: customTitle, workers: hrtiDownloadWorkers })
      });
      if (res.ok) {
        showToast("HRTi preuzimanje pokrenuto!");
      } else {
        showToast("Greška pri slanju preuzimanja", "error");
      }
    } catch (e: any) {
      showToast(e.message || "Greška na serveru", "error");
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

  // F2: Retry failed task — re-add same title as new download
  const retryDownloadTask = async (task: DownloadTask) => {
    showToast(`Pokušaj ponovnog pokretanja: ${task.title}`, "info");
    // We can only re-queue from frontend if we knew the original cmd;
    // best UX: show info that user should re-submit from the tab
    showToast("Ponovo pošaljite isti zahtev iz odgovarajućeg taba.", "info");
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
      
      {/* V4: Toast — type-based glow color */}
      {toast && (
        <div className={`fixed top-6 right-6 z-50 flex items-center gap-3 px-5 py-4 rounded-lg glass-panel animate-slide ${
          toast.type === "error" ? "glow-red" : toast.type === "success" ? "glow-emerald" : "glow-indigo"
        }`}>
          {toast.type === "success" && <CheckCircle2 className="w-5 h-5 text-emerald-400 flex-shrink-0" />}
          {toast.type === "error" && <AlertCircle className="w-5 h-5 text-red-400 flex-shrink-0" />}
          {toast.type === "info" && <Info className="w-5 h-5 text-indigo-400 flex-shrink-0" />}
          <span className="text-sm font-medium">{toast.message}</span>
        </div>
      )}

      {/* ── LEFT SIDEBAR ── */}
      <aside className="w-64 glass-panel border-r border-glass flex flex-col justify-between p-6">
        <div>
          {/* Logo */}
          <div className="flex items-center gap-3 mb-10">
            <div className="w-10 h-10 rounded-xl bg-indigo-600 flex items-center justify-center glow-indigo">
              <Download className="w-5 h-5 text-white" />
            </div>
            <div>
              <h1 className="font-extrabold text-md tracking-wider text-white">M-DOWNLOADER</h1>
              <p className="text-[10px] text-indigo-400 font-bold tracking-widest">SUITE v1.0</p>
            </div>
          </div>

          {/* V2: Navigation with service-specific colors + V6: download count badge */}
          <nav className="flex flex-col gap-2">
            {SERVICE_META.map((tab) => {
              const Icon = tab.icon;
              const active = activeTab === tab.id;
              // Count active downloads per service
              const svcCount = tab.id !== "settings"
                ? downloads.filter(d => d.service === tab.id && (d.status === "downloading" || d.status === "pending")).length
                : 0;
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg text-sm font-semibold transition-all duration-200 ${
                    active
                      ? "bg-indigo-600 text-white glow-indigo"
                      : "text-text-secondary hover:bg-white/[0.03] hover:text-white"
                  }`}
                >
                  {/* V2: service-specific color on icon when inactive */}
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
        <div className="flex items-center justify-between p-4 rounded-lg bg-white/[0.02] border border-glass">
          <div className="flex items-center gap-2">
            <Server className="w-4 h-4 text-text-muted" />
            <span className="text-xs text-text-secondary font-semibold">Server:</span>
          </div>
          <span className="flex items-center gap-1.5 text-xs font-bold">
            <span className={`w-2.5 h-2.5 rounded-full ${connected ? "bg-emerald-500" : "bg-red-500 animate-pulse"}`}></span>
            {connected ? "Povezan" : "Diskonekt"}
          </span>
        </div>
      </aside>

      {/* ── MAIN CONTENT AREA ── */}
      {/* V8: key on main wrapper forces re-animation on tab change */}
      <main className="flex-1 p-10 overflow-y-auto max-h-screen">
        
        {/* VOYO TAB */}
        {activeTab === "voyo" && (
          <div key="voyo" className="tab-content">
            <h2 className="text-3xl font-extrabold mb-2 text-white">Voyo RS</h2>
            <p className="text-text-secondary mb-8">Preuzmite video sadržaj i serije sa Voyo.rs platforme.</p>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
              
              {/* Downloader Form */}
              <div className="md:col-span-2 glass-panel p-8 rounded-xl border border-glass flex flex-col gap-6">
                <div>
                  <label>Izaberite tip preuzimanja</label>
                  <div className="flex gap-4">
                    <button
                      onClick={() => { setVoyoMode("video"); setVoyoSeriesData(null); setVoyoEpisodesRange(""); }}
                      className={`flex-1 btn ${voyoMode === "video" ? "btn-primary" : "btn-secondary"}`}
                    >
                      <Film className="w-4 h-4" /> Film / Epizoda
                    </button>
                    {/* Bug 7 Fix: also reset voyoEpisodesRange when switching to series */}
                    <button
                      onClick={() => { setVoyoMode("series"); setVoyoEpisodesRange(""); }}
                      className={`flex-1 btn ${voyoMode === "series" ? "btn-primary" : "btn-secondary"}`}
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
                  <select value={voyoRes} onChange={(e) => setVoyoRes(e.target.value)}>
                    <option value="1080p">1080p (Full HD - podrazumevano)</option>
                    <option value="720p">720p (HD)</option>
                    <option value="480p">480p (SD)</option>
                  </select>
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
                        {voyoSeriesData.episodes.map((ep) => (
                          <label key={ep.id} className="flex items-center gap-3 p-2 rounded hover:bg-white/[0.02] cursor-pointer text-sm m-0 normal-case tracking-normal">
                            <input
                              type="checkbox"
                              className="w-4 h-4 cursor-pointer"
                              checked={selectedVoyoEpisodes.includes(ep.id)}
                              onChange={(e) => {
                                if (e.target.checked) {
                                  setSelectedVoyoEpisodes([...selectedVoyoEpisodes, ep.id]);
                                } else {
                                  setSelectedVoyoEpisodes(selectedVoyoEpisodes.filter(id => id !== ep.id));
                                }
                              }}
                            />
                            <span className="font-bold text-indigo-300 min-w-16">S{ep.season.toString().padStart(2, "0")}E{ep.episode.toString().padStart(2, "0")}</span>
                            <span className="flex-1 truncate text-white">{ep.title}</span>
                            <span className="text-xs text-text-muted">{ep.length_mins}m</span>
                            {ep.drm && <span title="DRM Zaštićeno"><Lock className="w-3.5 h-3.5 text-amber-500" /></span>}
                            {ep.has_subs && <span title="Titlovi dostupni"><FileText className="w-3.5 h-3.5 text-indigo-400" /></span>}
                          </label>
                        ))}
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

              </div>
            </div>
          </div>
        )}

        {/* HRTi TAB */}
        {activeTab === "hrti" && (
          <div key="hrti" className="tab-content">
            <h2 className="text-3xl font-extrabold mb-2 text-white">HRTi Catalog</h2>
            <p className="text-text-secondary mb-8">Pregledajte i pretražujte filmove i serije na HRTi servisu.</p>

            <div className="flex flex-col gap-6">
              
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
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                    {catItems.map((item) => (
                      <div key={item.id} className="glass-card p-5 flex flex-col justify-between gap-3">
                        {/* V5: Gradient thumbnail placeholder */}
                        <div className={`hrti-thumbnail ${item.type === "movie" ? "hrti-thumbnail-movie" : "hrti-thumbnail-series"}`}>
                          {item.type === "movie"
                            ? <Film className="w-8 h-8 hrti-thumbnail-icon text-indigo-300" />
                            : <Tv className="w-8 h-8 hrti-thumbnail-icon text-purple-300" />
                          }
                        </div>
                        <div>
                          <div className="flex items-center gap-2 mb-2">
                            <span className={`badge ${item.type === "movie" ? "badge-connected" : "badge-warning"}`}>
                              {item.type}
                            </span>
                          </div>
                          <h4 className="font-bold text-white text-base leading-snug line-clamp-2">{item.title}</h4>
                          <p className="text-[10px] text-text-muted font-mono mt-1 truncate">{item.id}</p>
                        </div>

                        <div className="flex gap-2">
                          {item.type === "series" ? (
                            <button
                              onClick={() => fetchHrtiSeriesEpisodes(item.id, item.title)}
                              className="btn btn-secondary w-full text-xs py-2"
                            >
                              <List className="w-3.5 h-3.5" />
                              Prikaži Epizode
                            </button>
                          ) : (
                            <button
                              onClick={() => startHrtiDownload(item.id, item.title)}
                              className="btn btn-primary w-full text-xs py-2"
                            >
                              <Download className="w-3.5 h-3.5" />
                              Preuzmi Video
                            </button>
                          )}
                        </div>
                      </div>
                    ))}
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
          </div>
        )}

        {/* EON TAB */}
        {activeTab === "eon" && (
          <div key="eon" className="tab-content">
            <h2 className="text-3xl font-extrabold mb-2 text-white">EON TV</h2>
            <p className="text-text-secondary mb-8">EON integracija za preuzimanje VOD sadržaja, serija i TV kanala uživo sa Widevine DRM dekripcijom i API katalogom.</p>

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
                  <div className="flex gap-4">
                    {["vod", "series", "live"].map((mode) => (
                      <button
                        key={mode}
                        onClick={() => { setEonMode(mode as any); setEonTarget(""); }}
                        className={`flex-1 btn ${eonMode === mode ? "btn-primary" : "btn-secondary"}`}
                      >
                        {mode === "vod" && "VOD / URL"}
                        {mode === "series" && "Epizode / Serije"}
                        {mode === "live" && "TV Uživo (Live)"}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Bug 2 Fix: Live mode shows ONLY select, no duplicate input */}
                {eonMode === "live" ? (
                  <div>
                    <label>Izaberite TV Kanal</label>
                    <select
                      value={eonTarget}
                      onChange={(e) => setEonTarget(e.target.value)}
                    >
                      <option value="">-- Izaberi kanal iz liste --</option>
                      {eonChannels.map((c) => (
                        <option key={c} value={c}>{c}</option>
                      ))}
                    </select>
                    <p className="text-[10px] text-text-muted mt-1.5">Lista se čita iz eon_channels.json ako ga napravite u rootu aplikacije ili ~/.videodownload.</p>
                    <input
                      type="text"
                      className="mt-3"
                      placeholder="ili nalepite direktan live URL (.m3u8/.mpd)"
                      value={isUrlLike(eonTarget) ? eonTarget : ""}
                      onChange={(e) => setEonTarget(e.target.value)}
                    />
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
                    </div>
                  ) : (
                    <div className="flex flex-col gap-3">
                      <span className="badge badge-warning">Nije spreman</span>
                      <p className="text-xs text-text-secondary">{eonStatus?.error || "Registrujte EON nalog i proverite engine/dependencies."}</p>
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
            <h2 className="text-3xl font-extrabold mb-2 text-white">RTS Planeta</h2>
            <p className="text-text-secondary mb-8">Preuzimanje filmova i epizoda serija sa RTS Planeta platforme.</p>

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
              </div>
            </div>
          </div>
        )}

        {/* HBO MAX TAB */}
        {activeTab === "hbo" && (
          <div key="hbo" className="tab-content">
            <h2 className="text-3xl font-extrabold mb-2 text-white">HBO Max</h2>
            <p className="text-text-secondary mb-8">Prijava na HBO Max i preuzimanje videa po ID-u.</p>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
              
              <div className="md:col-span-2 flex flex-col gap-6">
                
                {/* Login trigger card */}
                <div className="glass-panel p-8 rounded-xl border border-glass flex flex-col gap-6">
                  <h3 className="font-extrabold text-lg text-white">Prijava (Login)</h3>
                  <p className="text-xs text-text-secondary">
                    HBO koristi autentifikaciju preko koda. Klikom na dugme pokrećete sesiju u pozadini koja će izgenerisati kod za prijavu. Detaljan kod i link ćete videti otvaranjem <strong>Logs</strong> dugmeta na kartici prijave u redu preuzimanja!
                  </p>
                  
                  <div className="flex gap-4 items-end">
                    <div className="flex-1">
                      <label>Region / Tržište (Market)</label>
                      <select value={hboMarket} onChange={(e) => setHboMarket(e.target.value)}>
                        <option value="emea">EMEA (Evropa - podrazumevano)</option>
                        <option value="us">US (Amerika)</option>
                      </select>
                    </div>
                    
                    <button
                      onClick={startHboLogin}
                      className="btn btn-secondary py-3 px-6 h-[46px]"
                    >
                      Pokreni Prijavu
                    </button>
                  </div>
                </div>

                {/* Downloader Form */}
                <div className="glass-panel p-8 rounded-xl border border-glass flex flex-col gap-6">
                  <h3 className="font-extrabold text-lg text-white">Preuzimanje Videa</h3>
                  
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

                  {/* F6: Show active market */}
                  <div className="mt-4 pt-4 border-t border-glass flex items-center gap-2">
                    <Globe className="w-4 h-4 text-text-muted" />
                    <span className="text-xs text-text-secondary">Market: <span className="font-bold text-white uppercase">{hboMarket}</span></span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* SETTINGS TAB */}
        {activeTab === "settings" && (
          <div key="settings" className="tab-content">
            <h2 className="text-3xl font-extrabold mb-2 text-white">Postavke Aplikacije</h2>
            <p className="text-text-secondary mb-8">Podesite kredencijale, izlazni direktorijum i putanje do alata.</p>

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
                  />
                  <p className="text-[10px] text-text-muted mt-1.5">* Svi preuzeti MKV video fajlovi biće sačuvani na ovoj lokaciji.</p>
                </div>

                <div className="border-t border-glass pt-6">
                  <h4 className="font-bold text-sm text-white mb-4">Detektovani Eksterni Alati & CDM</h4>
                  
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {status && Object.entries(status.binaries).map(([name, info]) => {
                      const display = name.toUpperCase().replace("_", ".");
                      return (
                        <div key={name} className="flex flex-col gap-2 p-4 rounded-lg bg-white/[0.02] border border-glass">
                          <div className="flex justify-between items-center">
                            <span className="text-sm font-bold text-white">{display}</span>
                            <span className={`badge ${info.found ? "badge-connected" : "badge-missing"}`}>
                              {info.found ? "Pronađen" : "Nedostaje"}
                            </span>
                          </div>
                          
                          <input
                            type="text"
                            value={binariesPaths[name] || ""}
                            onChange={(e) => setBinariesPaths({ ...binariesPaths, [name]: e.target.value })}
                            className="py-1.5 px-3 text-xs font-mono"
                          />
                        </div>
                      );
                    })}
                  </div>
                </div>

                <button onClick={handleSaveConfig} className="btn btn-primary self-end">
                  Sačuvaj Podešavanja
                </button>
              </div>

              {/* Service Credentials Manager */}
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
                      <input type="email" value={voyoEmail} onChange={(e) => setVoyoEmail(e.target.value)} placeholder="email@voyo.rs" />
                    </div>
                    <div>
                      <label>Lozinka</label>
                      <input type="password" value={voyoPassword} onChange={(e) => setVoyoPassword(e.target.value)} placeholder="••••••••" />
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
                      <input type="email" value={hrtiEmail} onChange={(e) => setHrtiEmail(e.target.value)} placeholder="email@hrti.hr" />
                    </div>
                    <div>
                      <label>Lozinka</label>
                      <input type="password" value={hrtiPassword} onChange={(e) => setHrtiPassword(e.target.value)} placeholder="••••••••" />
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
                        <input type="text" value={eonUsername} onChange={(e) => setEonUsername(e.target.value)} placeholder="npr. sbb_user@email.com" />
                      </div>
                      <div>
                        <label>Lozinka</label>
                        <input type="password" value={eonPassword} onChange={(e) => setEonPassword(e.target.value)} placeholder="••••••••" />
                      </div>
                      <div>
                        <label>Device Serial (Serijski Broj)</label>
                        <input type="text" value={eonSerial} onChange={(e) => setEonSerial(e.target.value)} placeholder="kopiraj iz payload-a" />
                        <p className="text-[10px] text-text-muted mt-1">Vrednost koju vidite kao device-serial u EON browser network payload-u.</p>
                      </div>
                      <div>
                        <label>Device Number (Broj Uređaja)</label>
                        <input type="text" value={eonNumber} onChange={(e) => setEonNumber(e.target.value)} placeholder="kopiraj iz response-a" />
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
                          className="font-mono text-xs flex-1"
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
                      <input type="email" value={rtsEmail} onChange={(e) => setRtsEmail(e.target.value)} placeholder="email@rtsplaneta.rs" />
                    </div>
                    <div>
                      <label>Lozinka</label>
                      <input type="password" value={rtsPassword} onChange={(e) => setRtsPassword(e.target.value)} placeholder="••••••••" />
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

          {/* V1: Better empty state */}
          {downloads.length === 0 ? (
            <div className="flex flex-col items-center justify-center p-12 border border-dashed border-glass rounded-lg text-center">
              <Inbox className="w-10 h-10 text-text-muted mb-3" />
              <p className="text-xs text-text-secondary font-semibold">Nema aktivnih preuzimanja.</p>
              <p className="text-[10px] text-text-muted mt-1">Sadržaj koji pokrenete pojaviće se ovde.</p>
            </div>
          ) : (
            <div className="flex flex-col gap-4">
              {downloads.map((task) => {
                const colorMap = {
                  pending:     "border-indigo-500/20 text-indigo-400",
                  downloading: "border-indigo-500 text-white",
                  finished:    "border-emerald-500/20 text-emerald-400",
                  failed:      "border-red-500/20 text-red-400",
                  cancelled:   "border-text-muted/20 text-text-secondary"
                };
                
                return (
                  <div key={task.id} className={`p-4 rounded-xl border bg-white/[0.01] flex flex-col gap-3 ${colorMap[task.status]}`}>
                    
                    <div className="flex justify-between items-start gap-2">
                      <div>
                        <div className="flex items-center gap-2 mb-1.5">
                          <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-white/[0.04] text-indigo-300 border border-glass uppercase">
                            {task.service}
                          </span>
                          <span className="text-[10px] font-bold uppercase tracking-wider">
                            {task.status}
                          </span>
                        </div>
                        <h4 className="font-bold text-xs leading-snug line-clamp-2 text-white">{task.title}</h4>
                      </div>

                      {/* Cancel task button */}
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

                    {/* V3: Progress bar with shimmer animation */}
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

                    {/* F2: Retry button for failed tasks */}
                    {task.status === "failed" && (
                      <button
                        onClick={() => retryDownloadTask(task)}
                        className="flex items-center justify-center gap-1.5 py-1.5 w-full rounded bg-red-500/10 border border-red-500/20 text-[10px] font-bold text-red-400 hover:bg-red-500/20 transition duration-200"
                      >
                        <RefreshCw className="w-3 h-3" />
                        Ponovi iz taba
                      </button>
                    )}

                    {/* Show logs button */}
                    <button
                      onClick={() => {
                        setSelectedTask(task);
                        setShowLogModal(true);
                      }}
                      className="flex items-center justify-center gap-1.5 py-1.5 w-full rounded bg-white/[0.02] border border-glass text-[10px] font-bold text-indigo-400 hover:bg-indigo-600 hover:text-white transition duration-200"
                    >
                      <Terminal className="w-3 h-3" />
                      Pregled Logova
                    </button>

                  </div>
                );
              })}
            </div>
          )}
        </div>
      </aside>

      {/* ── TERMINAL LOGS MODAL ── */}
      {showLogModal && selectedTask && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-8">
          <div className="w-full max-w-4xl h-[600px] glass-panel border border-glass rounded-xl flex flex-col justify-between overflow-hidden shadow-2xl animate-slide">
            
            {/* Modal Header */}
            <div className="p-6 border-b border-glass flex justify-between items-center bg-black/20">
              <div>
                <div className="flex items-center gap-2">
                  <Terminal className="w-5 h-5 text-indigo-400" />
                  <h3 className="font-extrabold text-base text-white">Konzola Logova u Realnom Vremenu</h3>
                </div>
                <p className="text-[10px] text-text-muted mt-1 truncate max-w-md font-mono">{selectedTask.title} (ID: {selectedTask.id})</p>
              </div>
              
              <button
                onClick={() => { setShowLogModal(false); setSelectedTask(null); }}
                className="p-2 rounded-lg hover:bg-white/[0.05] text-text-secondary hover:text-white transition"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* V7: Modal Body / Log Area with color-coded lines */}
            <div className="flex-1 p-6 overflow-y-auto bg-[#07080c] font-mono text-xs leading-relaxed flex flex-col gap-1 border-b border-glass">
              {selectedTask.logs.length === 0 ? (
                <div className="flex items-center justify-center h-full text-text-muted font-sans font-semibold">
                  Čekanje na ispis konzole...
                </div>
              ) : (
                selectedTask.logs.map((line, idx) => (
                  <div
                    key={idx}
                    className={`whitespace-pre-wrap select-text ${getLogLineClass(line)}`}
                  >
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
                  onClick={() => { setShowLogModal(false); setSelectedTask(null); }}
                  className="btn btn-secondary text-xs py-2 px-4"
                >
                  Zatvori Konzolu
                </button>
              )}
            </div>

          </div>
        </div>
      )}

    </div>
  );
}
