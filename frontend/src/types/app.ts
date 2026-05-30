import type { CredentialsSecurityMap } from "../components/SecurityPanels";

export type ToastType = "success" | "error" | "info";

export type ServiceName = "voyo" | "hrti" | "eon" | "rts" | "hbo" | "hbomax" | "yt-dlp";

export type DownloadStatus = "pending" | "downloading" | "finished" | "failed" | "cancelled";

export interface BinaryStatus {
  found: boolean;
  path: string;
}

export interface ServiceStatus {
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

export interface AppStatus {
  binaries: Record<string, BinaryStatus>;
  output_dir: string;
  transcode_mode?: string;
  sniffer?: { auto_download?: boolean };
  credentials_security?: CredentialsSecurityMap;
  services: Record<string, ServiceStatus>;
  system_metrics?: {
    disk: { total: number; used: number; free: number; percent: number };
    cpu: { percent: number };
    ram: { total: number; used: number; free: number; percent: number };
  } | null;
}

export interface DownloadTask {
  id: string;
  service: string;
  title: string;
  status: DownloadStatus;
  progress: number;
  speed: string;
  eta: string;
  logs: string[];
}

export interface HrtiItem {
  id: string;
  type: string;
  title: string;
}

export interface VoyoEpisode {
  id: number;
  title: string;
  season: number;
  episode: number;
  length_mins: number;
  drm: boolean;
  has_subs: boolean;
}

export interface VoyoSeason {
  season: number;
  episodes: VoyoEpisode[];
}

export interface VoyoSeriesInfo {
  title: string;
  description: string;
  nbSeasons?: number;
  seasons?: VoyoSeason[];
  episodes: VoyoEpisode[];
}

export interface EonMediaItem {
  id?: string;
  title?: string;
  name?: string;
  url?: string;
  start?: string;
  end?: string;
  description?: string;
  duration_min?: number;
}

export interface ScheduledTask {
  id: string;
  title: string;
  channel_name: string;
  duration: number;
  start_time: string;
}

export interface SmartEpisode {
  id: number;
  title?: string;
  season?: number;
  episode?: number;
  length_mins?: number;
  drm?: boolean;
}

export interface SmartDetectData {
  service: string;
  title: string;
  target_id?: string;
  mode?: string;
  episodes?: SmartEpisode[];
  available_resolutions?: string[];
  available_subtitles?: string[];
  available_auto_subtitles?: string[];
  thumbnail?: string;
  description?: string;
  duration_str?: string;
  uploader?: string;
  view_count?: number;
  upload_date?: string;
}

export interface TranscodeAcceleration {
  supported: boolean;
  message?: string;
  label?: string;
  description?: string;
}

export interface TranscodeCodecInfo {
  supported: boolean;
  encoder_used?: string;
}

export interface TranscodeDiagnostics {
  gpu_name?: string;
  available_codecs?: {
    hevc?: TranscodeCodecInfo;
    av1?: TranscodeCodecInfo;
  };
  accelerations?: Record<string, TranscodeAcceleration>;
}

export interface SniffedItemEntry {
  manifestUrl?: string;
  licenseUrl?: string;
  title?: string;
  headers?: Record<string, string>;
}

export interface SnifferCapture {
  service: string;
  type: "manifest" | "license" | "ready";
  url: string;
  headers?: Record<string, string>;
  title?: string;
  manifestUrl?: string;
  licenseUrl?: string;
}

export interface SnifferReadyEntry {
  manifest_url?: string;
  license_url?: string;
  title?: string;
  ready?: boolean;
}

export interface RtsVideoInfo {
  title?: string;
  description?: string;
  thumbnail?: string;
}

export interface DrmHealth {
  cdm_ready: boolean;
  legacy_mode: boolean;
  wvd_file: string | null;
  wvd_metadata: {
    is_valid: boolean;
    wvd_version: number | null;
    device_type: string | null;
    security_level: number | null;
    security_level_name: string;
    private_key_size: number;
    client_id_size: number;
    file_size: number;
    error: string | null;
  };
  key_cache: { total_entries: number; alive_entries: number };
  provider_certs_fetched: string[];
  pywidevine_version: string | null;
  recommendations: string[];
}
