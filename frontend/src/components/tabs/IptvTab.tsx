import {
  Copy,
  Globe,
  Info,
  List,
  Play,
  Server,
  Terminal,
  Tv,
} from "lucide-react";
import { useIptvTab } from "../../hooks/domains/useIptvTab";


export function IptvTab() {
  const {
    eonChannels,
    showToast,
  } = useIptvTab();
  return (
<div key="iptv" className="tab-content tab-content-iptv">
    <div className="tab-page-header tab-header-eon mb-6">
      <div className="tab-page-header-icon" style={{background:"linear-gradient(135deg,#3b82f6,#2563eb)",boxShadow:"0 0 20px rgba(59,130,246,0.4)"}}>
        <Server style={{width:24,height:24,color:"white"}} />
      </div>
      <div style={{flex:1}}>
        <h2 className="text-lg font-extrabold text-white mb-1 flex items-center gap-2">
          <Server className="w-5 h-5 text-blue-400" /> Kućni IPTV Streaming Centar
        </h2>
        <p className="text-xs text-text-muted">
          Pretvorite svoj računar u 24/7 lokalni IPTV server za VLC, Kodi, PotPlayer ili Smart TV.
        </p>
      </div>
      <div className="flex items-center gap-2 bg-emerald-500/10 border border-emerald-500/20 px-3 py-1.5 rounded-xl">
        <span className="relative flex h-2 w-2">
          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
          <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
        </span>
        <span className="text-[10px] font-bold text-emerald-400 tracking-wider uppercase">Online</span>
      </div>
    </div>

    <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
      {/* Lefty card: Server details */}
      <div className="md:col-span-2 flex flex-col gap-5">
        <div className="smart-console-card">
          <h3 className="text-sm font-bold text-white mb-4 flex items-center gap-2 border-b border-white/5 pb-2">
            <Globe className="w-4 h-4 text-blue-400" /> Pristupna M3U Plejlista
          </h3>
          <p className="text-xs text-text-muted mb-4 leading-relaxed">
            Kopirajte donju adresu i unesite je u svoj omiljeni media plejer (npr. VLC, Kodi ili IPTV aplikaciju na Smart TV-u) za gledanje EON kanala uživo bez preuzimanja!
          </p>
          
          <div className="flex items-center gap-2 bg-black/35 border border-white/10 rounded-xl p-3 mb-4">
            <input 
              type="text" 
              readOnly 
              value={`${window.location.protocol}//${window.location.hostname}${window.location.port ? ':' + window.location.port : ''}/api/iptv/playlist.m3u`}
              className="bg-transparent text-xs text-blue-300 font-mono flex-1 outline-none border-none"
            />
            <button 
              onClick={() => {
                const url = `${window.location.protocol}//${window.location.hostname}${window.location.port ? ':' + window.location.port : ''}/api/iptv/playlist.m3u`;
                navigator.clipboard.writeText(url);
                showToast("M3U plejlista kopirana u međuspremnik!");
              }}
              className="p-1.5 hover:bg-white/10 rounded-lg text-text-muted hover:text-white transition-all flex items-center gap-1"
              title="Kopiraj link"
            >
              <Copy className="w-3.5 h-3.5" />
              <span className="text-[10px] font-semibold">Kopiraj</span>
            </button>
          </div>

          <div className="flex items-center gap-2 text-xs text-text-muted bg-white/5 border border-white/5 p-3 rounded-xl">
            <Info className="w-4 h-4 text-blue-400 shrink-0" />
            <span>
              FFmpeg radi automatsku transmuksaciju i prilagođavanje u realnom vremenu sa <strong>ultraniskom latencijom</strong>.
            </span>
          </div>
        </div>

        {/* Available Channels catalog grid */}
        <div className="smart-console-card">
          <h3 className="text-sm font-bold text-white mb-4 flex items-center gap-2 border-b border-white/5 pb-2">
            <List className="w-4 h-4 text-emerald-400" /> Dostupni IPTV Kanali
          </h3>
          
          {eonChannels.length === 0 ? (
            <div className="text-center py-6 text-text-muted text-xs">
              Nema konfigurisanih kanala. Prijavite se na EON TV tabu za automatsko učitavanje kanala.
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {eonChannels.map((channel: string, idx: number) => (
                <div key={idx} className="flex items-center justify-between bg-white/5 hover:bg-white/10 border border-white/5 rounded-xl p-3 transition-all">
                  <div className="flex items-center gap-2">
                    <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse"></span>
                    <span className="text-xs font-semibold text-white">{channel}</span>
                  </div>
                  <a 
                    href={`${window.location.protocol}//${window.location.hostname}${window.location.port ? ':' + window.location.port : ''}/api/iptv/stream/eon/${encodeURIComponent(channel)}`}
                    target="_blank" 
                    rel="noopener noreferrer"
                    className="text-[10px] text-blue-400 hover:text-blue-300 font-semibold flex items-center gap-1 border border-blue-500/20 hover:border-blue-500/40 px-2.5 py-1 rounded-lg bg-blue-500/5 transition-all"
                  >
                    <Play className="w-3 h-3 fill-blue-400" /> Pokreni
                  </a>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Righty column: Instructions / Info card */}
      <div className="flex flex-col gap-5">
        <div className="smart-console-card">
          <h3 className="text-sm font-bold text-white mb-3 flex items-center gap-2">
            <Tv className="w-4 h-4 text-indigo-400" /> Kako koristiti?
          </h3>
          <ol className="text-xs text-text-muted flex flex-col gap-3 list-decimal pl-4">
            <li>Kopirajte link pristupne M3U plejliste.</li>
            <li>Otvorite <strong>VLC Media Player</strong>, pritisnite <kbd className="bg-white/10 px-1 py-0.5 rounded text-[10px]">Ctrl+N</kbd> (Mrežni tok).</li>
            <li>Nalijepite kopirani link i kliknite <strong>Slušaj/Pusti</strong>.</li>
            <li>Svi kanali se pojavljuju u vašoj VLC plejlisti (pritisnite <kbd className="bg-white/10 px-1 py-0.5 rounded text-[10px]">Ctrl+L</kbd>).</li>
          </ol>
        </div>

        <div className="smart-console-card">
          <h3 className="text-sm font-bold text-white mb-3 flex items-center gap-2">
            <Terminal className="w-4 h-4 text-purple-400" /> Server Statistika
          </h3>
          <div className="flex flex-col gap-2.5 text-xs text-text-muted">
            <div className="flex justify-between">
              <span>Protokol:</span>
              <span className="font-mono text-white">HLS / MPEG-TS</span>
            </div>
            <div className="flex justify-between">
              <span>Aktivni klijenti:</span>
              <span className="font-semibold text-emerald-400">0 (Lokalna mreža)</span>
            </div>
            <div className="flex justify-between">
              <span>Dekodiranje:</span>
              <span className="font-semibold text-blue-400">FFmpeg stream copy</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
  );
}
