export interface YtdlpTheme {
  color: string;
  glow: string;
  emoji: string;
  name: string;
}

export const YTDLP_THEME: YtdlpTheme = {
  color: "#3b82f6",
  glow: "rgba(59,130,246,0.08)",
  emoji: "🌐",
  name: "Univerzalno",
};

export const YTDLP_PLATFORM_EXAMPLES = [
  { label: "YouTube", url: "https://www.youtube.com/watch?v=dQw4w9WgXcQ" },
  { label: "X / Twitter", url: "https://x.com/i/status/1" },
  { label: "TikTok", url: "https://www.tiktok.com/@user/video/1" },
  { label: "Vimeo", url: "https://vimeo.com/148751763" },
] as const;
