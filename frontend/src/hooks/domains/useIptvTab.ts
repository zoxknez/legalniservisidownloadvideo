import { useCallback, useEffect, useState } from "react";
import { useAppShellSlice, useAppStatus, useEonSlice } from "../../context/appStore";
import { apiFetch } from "../../lib/api";

interface IptvStatus {
  ready: boolean;
  eon_authenticated: boolean;
  ffmpeg_found: boolean;
  channel_count: number;
  active_streams: Record<string, number>;
  active_stream_count: number;
}

export function useIptvTab() {
  const { eonChannels } = useEonSlice();
  const { showToast } = useAppShellSlice();
  const appStatus = useAppStatus();
  const [iptvStatus, setIptvStatus] = useState<IptvStatus | null>(null);
  const [iptvLoading, setIptvLoading] = useState(false);

  const fetchIptvStatus = useCallback(async () => {
    setIptvLoading(true);
    try {
      const res = await apiFetch("/api/iptv/status");
      if (res.ok) {
        setIptvStatus(await res.json());
      }
    } catch {
      /* ignore */
    } finally {
      setIptvLoading(false);
    }
  }, []);

  useEffect(() => {
    void fetchIptvStatus();
  }, [fetchIptvStatus]);

  const playlistUrl = `${window.location.protocol}//${window.location.hostname}${window.location.port ? ":" + window.location.port : ""}/api/iptv/playlist.m3u`;

  const copyPlaylistUrl = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(playlistUrl);
      showToast("M3U plejlista kopirana u međuspremnik!", "success");
    } catch {
      showToast("Nije moguće kopirati — proverite dozvole za clipboard.", "error");
    }
  }, [playlistUrl, showToast]);

  return {
    eonChannels,
    showToast,
    appStatus,
    iptvStatus,
    iptvLoading,
    playlistUrl,
    copyPlaylistUrl,
    fetchIptvStatus,
  };
}
