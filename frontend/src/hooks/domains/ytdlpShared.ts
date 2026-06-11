import type { SmartDetectData, SmartEpisode } from "../../types/app";

export function applyYtdlpDetectDefaults(
  data: SmartDetectData,
  setters: {
    setResolution: (v: string) => void;
    setSubs: (v: string) => void;
    setDownloadPlaylist: (v: boolean) => void;
  },
) {
  if (data.available_resolutions?.length) {
    setters.setResolution(data.available_resolutions[0]);
  } else {
    setters.setResolution("1080p");
  }
  if (data.mode === "playlist") {
    setters.setDownloadPlaylist(true);
  }
  const manual = data.available_subtitles || [];
  const auto = data.available_auto_subtitles || [];
  const priority = ["sr", "hr", "bs", "en"];
  const matchedManual = manual.filter((l) => priority.includes(l.toLowerCase()));
  const matchedAuto = auto.filter((l) => priority.includes(l.toLowerCase()));
  if (matchedManual.length > 0) {
    setters.setSubs(matchedManual.join(","));
  } else if (matchedAuto.length > 0) {
    setters.setSubs(matchedAuto.join(","));
  } else if (manual.length > 0) {
    setters.setSubs(manual.slice(0, 2).join(","));
  } else {
    setters.setSubs("");
  }
}

export function buildYtdlpDownloadBody(
  data: SmartDetectData,
  opts: {
    resolution: string;
    subs: string;
    audioOnly: boolean;
    useAria2: boolean;
    hardsub: boolean;
    cookiesBrowser: string | null;
    cookiesConfigured: boolean;
    impersonate: boolean;
    proxy: string | null;
    geoBypass: boolean;
    embedThumbnail: boolean;
    embedMetadata: boolean;
    limitRate: string | null;
    formatSpec: string | null;
    extractorArgs: string | null;
    sponsorblockMode: string;
    splitChapters: boolean;
    downloadPlaylist: boolean;
    playlistItems: string | null;
    selectedEpisodes: (number | string)[];
  },
) {
  let downloadPlaylist = opts.downloadPlaylist;
  let playlistItems = opts.playlistItems;
  if (data.mode === "playlist" && data.episodes?.length) {
    downloadPlaylist = true;
    if (
      opts.selectedEpisodes.length > 0 &&
      opts.selectedEpisodes.length < data.episodes.length
    ) {
      const nums = data.episodes
        .map((ep: SmartEpisode, idx: number) =>
          opts.selectedEpisodes.includes(ep.id) ? String(ep.episode ?? idx + 1) : null,
        )
        .filter((n): n is string => n != null);
      playlistItems = nums.join(",");
    }
  }
  return {
    url: data.target_id,
    video_title: data.title || null,
    resolution: opts.resolution,
    subs: opts.subs,
    audio_only: opts.audioOnly,
    use_aria2: opts.useAria2,
    hardsub: opts.hardsub,
    cookies_browser: opts.cookiesConfigured ? null : opts.cookiesBrowser,
    impersonate_browser: opts.impersonate,
    proxy: opts.proxy,
    geo_bypass: opts.geoBypass,
    embed_thumbnail: opts.embedThumbnail,
    embed_metadata: opts.embedMetadata,
    limit_rate: opts.limitRate,
    format_spec: opts.formatSpec,
    extractor_args: opts.extractorArgs,
    sponsorblock_mode: opts.sponsorblockMode,
    split_chapters: opts.splitChapters,
    download_playlist: downloadPlaylist,
    playlist_items: playlistItems,
  };
}
