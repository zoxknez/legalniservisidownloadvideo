import type { CredentialsSecurityMap } from "../components/SecurityPanels";

export type ToastType = "success" | "error" | "info";

export type ServiceName = "voyo" | "hrti" | "eon" | "rts" | "hbo" | "hbomax" | "skyshowtime" | "ytdlp";

export type DownloadStatus = "pending" | "downloading" | "finished" | "failed" | "cancelled";

export interface BinaryStatus {
  found: boolean;
  path: string;
}

export interface ServiceStatus {
  authenticated: boolean;
  ready?: boolean;
  variant?: string;
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
  ytdlp_version?: string;
  node_available?: boolean;
  serial?: string;
  number?: string;
  market?: string;
  token_path?: string;
  script_path?: string;
  missing?: string[];
  optional_missing?: string[];
}

export interface DrmStatusSummary {
  cdm_ready: boolean;
  legacy_mode: boolean;
  wvd_file: string | null;
  security_level_name?: string;
  key_cache_alive?: number;
}

export interface AppStatus {
  binaries: Record<string, BinaryStatus>;
  output_dir: string;
  transcode_mode?: string;
  ytdlp_name_template?: string;
  max_concurrent_downloads?: number;
  browser_sync_supported?: boolean;
  server?: {
    api_key_configured?: boolean;
    localhost_bypass?: boolean;
  };
  sniffer?: { auto_download?: boolean };
  voyo_ignore_catalog_drm_hint?: boolean;
  credentials_security?: CredentialsSecurityMap;
  drm?: DrmStatusSummary;
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

export interface HrtiCategory {
  id: string;
  name: string;
}

export interface HrtiSeason {
  season: number;
  title: string;
  episode_count: number;
}

export interface HrtiItem {
  id: string;
  type: "movie" | "series" | "episode";
  title: string;
  thumbnail?: string;
  season?: number;
  episode?: number;
  category_id?: string;
}

export interface VoyoEpisode {
  id: number;
  title: string;
  season: number;
  episode: number;
  length_mins: number;
  /** Katalog hint (drmProtected) — nije autoritativan. */
  drm: boolean;
  drm_hint?: boolean;
  drm_blocking?: boolean;
  streamable?: boolean;
  probe_ok?: boolean;
  stream_reason?: string;
  has_subs: boolean;
}

export interface VoyoSeason {
  season: number;
  episodes: VoyoEpisode[];
}

export interface VoyoSeriesInfo {
  success?: boolean;
  title: string;
  description: string;
  nbSeasons?: number;
  seasons?: VoyoSeason[];
  episodes: VoyoEpisode[];
}

export interface VoyoVideoInfo {
  success?: boolean;
  id?: number;
  title: string;
  description?: string;
  duration_str?: string;
  thumbnail?: string;
  drm?: boolean;
  drm_hint?: boolean;
  drm_blocking?: boolean;
  streamable?: boolean;
  probe_ok?: boolean;
  drm_type?: string;
  stream_reason?: string;
  has_subs?: boolean;
}

export interface SkyShowtimeEpisode {
  id: string;
  title: string;
  season: number;
  episode: number;
  length_mins: number;
  drm: boolean;
  has_subs?: boolean;
}

export interface SkyShowtimeSeason {
  season: number;
  episodes: SkyShowtimeEpisode[];
}

export interface SkyShowtimeSeriesInfo {
  success?: boolean;
  title: string;
  description: string;
  nbSeasons?: number;
  seasons?: SkyShowtimeSeason[];
  episodes: SkyShowtimeEpisode[];
  series_url?: string;
  slug?: string;
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
  id: number | string;
  title?: string;
  season?: number;
  episode?: number;
  length_mins?: number;
  drm?: boolean;
  drm_hint?: boolean;
  drm_blocking?: boolean;
  streamable?: boolean;
  probe_ok?: boolean;
  stream_reason?: string;
}

export interface SmartDetectData {
  service: string;
  title: string;
  target_id?: string;
  mode?: string;
  episodes?: SmartEpisode[];
  seasons?: VoyoSeason[];
  available_resolutions?: string[];
  available_subtitles?: string[];
  available_auto_subtitles?: string[];
  thumbnail?: string;
  description?: string;
  duration_str?: string;
  uploader?: string;
  view_count?: number;
  like_count?: number;
  upload_date?: string;
  metadata_partial?: boolean;
  generic_url?: boolean;
  playlist_count?: number;
  drm?: boolean;
  drm_hint?: boolean;
  drm_blocking?: boolean;
  streamable?: boolean;
  probe_ok?: boolean;
  drm_type?: string;
  stream_reason?: string;
  has_subs?: boolean;
}

export interface VoyoProfile {
  profileId: number;
  name: string;
  type?: string;
  avatar?: string;
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
