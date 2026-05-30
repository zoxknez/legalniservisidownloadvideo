import {
  Download,
  Server,
} from "lucide-react";
import { SERVICE_META } from "../../constants/services";
import type { DownloadTask } from "../../types/app";
import { useAppShell } from "../../hooks/domains/useAppShell";
import { prefetchTab } from "../../utils/tabPrefetch";

export function AppSidebar() {
  const { activeTab, setActiveTab, downloads, connected } = useAppShell();
  return (
<aside className="w-64 glass-panel border-r border-glass flex flex-col justify-between p-6 bg-gradient-to-b from-[#11121c] to-[#0a0b10]">
  <div>
    <div className="flex items-center gap-3 mb-10 group cursor-pointer" onClick={() => setActiveTab("dashboard")}>
      <div className="w-11 h-11 rounded-xl bg-gradient-to-tr from-indigo-500 via-purple-500 to-pink-500 flex items-center justify-center glow-indigo shadow-lg transition-all duration-300 group-hover:scale-105 group-hover:shadow-[0_0_20px_rgba(99,102,241,0.5)]">
        <Download className="w-5 h-5 text-white transition-transform duration-500 group-hover:rotate-12 group-hover:scale-110" />
      </div>
      <div className="flex flex-col">
        <h1 className="font-black text-sm tracking-wide text-white group-hover:text-indigo-400 transition-colors duration-200">
          <span className="bg-clip-text bg-gradient-to-r from-indigo-400 via-purple-300 to-white">o0o0o0o</span>-downloader
        </h1>
        <span className="text-[9px] font-black tracking-widest text-indigo-400 uppercase">
          PREMIUM ARCHIVER
        </span>
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
          ? downloads.filter((d: DownloadTask) => d.service === svcFilter && (d.status === "downloading" || d.status === "pending")).length
          : 0;
        return (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            onMouseEnter={() => prefetchTab(tab.id)}
            onFocus={() => prefetchTab(tab.id)}
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
  );
}
