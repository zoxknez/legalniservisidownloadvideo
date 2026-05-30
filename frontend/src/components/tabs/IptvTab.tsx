import {
  AlertTriangle,
  Check,
  Copy,
  Globe,
  Info,
  List,
  Loader2,
  Play,
  RefreshCw,
  Server,
  Terminal,
  Tv,
} from "lucide-react";
import { useIptvTab } from "../../hooks/domains/useIptvTab";

export function IptvTab() {
  const {
    eonChannels,
    iptvStatus,
    iptvLoading,
    playlistUrl,
    copyPlaylistUrl,
    fetchIptvStatus,
  } = useIptvTab();

  const isReady = iptvStatus?.ready ?? false;
  const eonAuth = iptvStatus?.eon_authenticated ?? false;
  const ffmpegOk = iptvStatus?.ffmpeg_found ?? false;
  const activeCount = iptvStatus?.active_stream_count ?? 0;
  const channelCount = iptvStatus?.channel_count ?? eonChannels.length;

  return (
    <div key="iptv" className="tab-content tab-content-iptv">
      <div className="tab-page-header tab-header-iptv mb-6">
        <div className="tab-page-header-icon" style={{ background: "linear-gradient(135deg,#3b82f6,#2563eb)", boxShadow: "0 0 20px rgba(59,130,246,0.4)" }}>
          <Server style={{ width: 24, height: 24, color: "white" }} />
        </div>
        <div style={{ flex: 1 }}>
          <h2 className="text-lg font-extrabold text-white mb-1 flex items-center gap-2">
            <Server className="w-5 h-5 text-blue-400" /> Kućni IPTV Streaming Centar
          </h2>
          <p className="text-xs text-text-muted">
            Pretvorite svoj računar u lokalni IPTV server za VLC, Kodi, PotPlayer ili Smart TV.
          </p>
        </div>
        {iptvLoading ? (
          <div className="flex items-center gap-2 bg-white/5 border border-white/10 px-3 py-1.5 rounded-xl">
            <Loader2 className="w-3 h-3 text-text-muted animate-spin" />
            <span className="text-[10px] font-bold text-text-muted tracking-wider uppercase">Provera...</span>
          </div>
        ) : isReady ? (
          <div className="flex items-center gap-2 bg-emerald-500/10 border border-emerald-500/20 px-3 py-1.5 rounded-xl">
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
            </span>
            <span className="text-[10px] font-bold text-emerald-400 tracking-wider uppercase">Online</span>
          </div>
        ) : (
          <div className="flex items-center gap-2 bg-amber-500/10 border border-amber-500/20 px-3 py-1.5 rounded-xl">
            <AlertTriangle className="w-3 h-3 text-amber-400" />
            <span className="text-[10px] font-bold text-amber-400 tracking-wider uppercase">Nije spreman</span>
          </div>
        )}
      </div>

      {/* Warnings */}
      {!iptvLoading && !isReady && (
        <div className="mb-5 flex flex-col gap-2">
          {!eonAuth && (
            <div className="flex items-center gap-2 bg-amber-500/8 border border-amber-500/15 rounded-xl px-4 py-2.5 text-xs text-amber-300">
              <AlertTriangle className="w-4 h-4 shrink-0" />
              <span>EON TV nalog nije prijavljen. Idite na <strong>EON TV</strong> tab i prijavite se za pristup kanalima.</span>
            </div>
          )}
          {!ffmpegOk && (
            <div className="flex items-center gap-2 bg-rose-500/8 border border-rose-500/15 rounded-xl px-4 py-2.5 text-xs text-rose-300">
              <AlertTriangle className="w-4 h-4 shrink-0" />
              <span>FFmpeg nije pronađen. Proverite putanju u <strong>Postavkama</strong> za ispravan IPTV streaming.</span>
            </div>
          )}
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
        {/* Left: Server details */}
        <div className="md:col-span-2 flex flex-col gap-5">
          <div className="smart-console-card">
            <h3 className="text-sm font-bold text-white mb-4 flex items-center gap-2 border-b border-white/5 pb-2">
              <Globe className="w-4 h-4 text-blue-400" /> Pristupna M3U Plejlista
            </h3>
            <p className="text-xs text-text-muted mb-4 leading-relaxed">
              Kopirajte donju adresu i unesite je u svoj omiljeni media plejer (npr. VLC, Kodi ili IPTV aplikaciju na Smart TV-u) za gledanje EON kanala uživo.
            </p>

            <div className="flex items-center gap-2 bg-black/35 border border-white/10 rounded-xl p-3 mb-4">
              <input
                type="text"
                readOnly
                value={playlistUrl}
                className="bg-transparent text-xs text-blue-300 font-mono flex-1 outline-none border-none"
              />
              <button
                onClick={copyPlaylistUrl}
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
                FFmpeg radi automatsku transmuksaciju i prilagođavanje u realnom vremenu. API ključ je ugrađen u M3U link za pristup sa LAN uređaja.
              </span>
            </div>
          </div>

          {/* Channel catalog */}
          <div className="smart-console-card">
            <div className="flex items-center justify-between mb-4 border-b border-white/5 pb-2">
              <h3 className="text-sm font-bold text-white flex items-center gap-2">
                <List className="w-4 h-4 text-emerald-400" /> Dostupni IPTV Kanali
                {channelCount > 0 && (
                  <span className="text-[10px] font-bold text-text-muted bg-white/5 px-2 py-0.5 rounded-full">{channelCount}</span>
                )}
              </h3>
              <button
                onClick={fetchIptvStatus}
                className="text-[10px] text-text-muted hover:text-white flex items-center gap-1 transition-colors"
                title="Osveži status"
              >
                <RefreshCw className="w-3 h-3" /> Osveži
              </button>
            </div>

            {eonChannels.length === 0 ? (
              <div className="text-center py-8 text-text-muted text-xs flex flex-col items-center gap-3">
                <Tv className="w-8 h-8 text-white/10" />
                <p>Nema konfigurisanih kanala.</p>
                <p className="text-text-muted/60">Prijavite se na <strong>EON TV</strong> tab za automatsko učitavanje liste kanala.</p>
              </div>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {eonChannels.map((channel: string) => (
                  <div key={channel} className="flex items-center justify-between bg-white/[0.03] hover:bg-white/[0.07] border border-white/5 rounded-xl p-3 transition-all">
                    <div className="flex items-center gap-2">
                      <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse shrink-0"></span>
                      <span className="text-xs font-semibold text-white truncate">{channel}</span>
                    </div>
                    <a
                      href={`${window.location.protocol}//${window.location.hostname}${window.location.port ? ":" + window.location.port : ""}/api/iptv/stream/eon/${encodeURIComponent(channel)}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-[10px] text-blue-400 hover:text-blue-300 font-semibold flex items-center gap-1 border border-blue-500/20 hover:border-blue-500/40 px-2.5 py-1 rounded-lg bg-blue-500/5 transition-all shrink-0"
                    >
                      <Play className="w-3 h-3 fill-blue-400" /> Stream
                    </a>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Right column */}
        <div className="flex flex-col gap-5">
          <div className="smart-console-card">
            <h3 className="text-sm font-bold text-white mb-3 flex items-center gap-2">
              <Tv className="w-4 h-4 text-indigo-400" /> Kako koristiti?
            </h3>
            <ol className="text-xs text-text-muted flex flex-col gap-3 list-decimal pl-4">
              <li>Kopirajte link pristupne M3U plejliste.</li>
              <li>Otvorite <strong>VLC Media Player</strong>, pritisnite <kbd className="bg-white/10 px-1 py-0.5 rounded text-[10px]">Ctrl+N</kbd> (Mrežni tok).</li>
              <li>Nalepite kopirani link i kliknite <strong>Pusti</strong>.</li>
              <li>Svi kanali se pojavljuju u VLC plejlisti (<kbd className="bg-white/10 px-1 py-0.5 rounded text-[10px]">Ctrl+L</kbd>).</li>
            </ol>
          </div>

          <div className="smart-console-card">
            <h3 className="text-sm font-bold text-white mb-3 flex items-center gap-2">
              <Terminal className="w-4 h-4 text-purple-400" /> Server Statistika
            </h3>
            <div className="flex flex-col gap-2.5 text-xs text-text-muted">
              <div className="flex justify-between">
                <span>Protokol:</span>
                <span className="font-mono text-white">MPEG-TS</span>
              </div>
              <div className="flex justify-between">
                <span>FFmpeg:</span>
                <span className={`font-semibold ${ffmpegOk ? "text-emerald-400" : "text-rose-400"}`}>
                  {ffmpegOk ? "Pronađen" : "Nije pronađen"}
                </span>
              </div>
              <div className="flex justify-between">
                <span>EON nalog:</span>
                <span className={`font-semibold ${eonAuth ? "text-emerald-400" : "text-amber-400"}`}>
                  {eonAuth ? "Prijavljen" : "Neprijavljen"}
                </span>
              </div>
              <div className="flex justify-between">
                <span>Kanali:</span>
                <span className="font-semibold text-blue-400">{channelCount}</span>
              </div>
              <div className="flex justify-between">
                <span>Aktivni streamovi:</span>
                <span className={`font-semibold ${activeCount > 0 ? "text-emerald-400" : "text-text-muted"}`}>{activeCount}</span>
              </div>
            </div>
          </div>

          <div className="smart-console-card">
            <h3 className="text-sm font-bold text-white mb-3 flex items-center gap-2">
              <Check className="w-4 h-4 text-emerald-400" /> Podržano
            </h3>
            <div className="flex flex-col gap-2 text-xs text-text-muted">
              <div className="flex items-center gap-2">
                <Check className="w-3.5 h-3.5 text-emerald-400" /> <span>VLC, Kodi, PotPlayer, mpv</span>
              </div>
              <div className="flex items-center gap-2">
                <Check className="w-3.5 h-3.5 text-emerald-400" /> <span>Smart TV IPTV aplikacije</span>
              </div>
              <div className="flex items-center gap-2">
                <Check className="w-3.5 h-3.5 text-emerald-400" /> <span>LAN pristup sa API ključem</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
