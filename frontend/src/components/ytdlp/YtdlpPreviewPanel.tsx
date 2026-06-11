import type { ReactNode } from "react";
import { Loader2 } from "lucide-react";
import type { SmartDetectData } from "../../types/app";
import { YtdlpEpisodeList } from "./YtdlpEpisodeList";
import { YtdlpPreviewHeader } from "./YtdlpPreviewHeader";
import { YTDLP_THEME } from "./ytdlpTheme";

export interface YtdlpPreviewPanelProps {
  data: SmartDetectData | null;
  loading?: boolean;
  selectedEpisodes: (number | string)[];
  setSelectedEpisodes: (ids: (number | string)[]) => void;
  subs?: string;
  setSubs?: (v: string) => void;
  children?: ReactNode;
}

export function YtdlpPreviewPanel({
  data,
  loading = false,
  selectedEpisodes,
  setSelectedEpisodes,
  subs,
  setSubs,
  children,
}: YtdlpPreviewPanelProps) {
  const theme = YTDLP_THEME;

  if (loading && !data) {
    return (
      <div
        className="smart-preview-panel glow-blue-card"
        style={{
          borderColor: "rgba(59,130,246,0.2)",
          padding: 32,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          gap: 16,
        }}
      >
        <Loader2
          style={{ width: 32, height: 32, color: theme.color, animation: "spin 1s linear infinite" }}
        />
        <p className="text-sm font-bold text-white">Analiziramo link...</p>
        <p className="text-xs text-text-muted">Ekstrakcija metapodataka i dostupnih formata</p>
      </div>
    );
  }

  if (!data) return null;

  return (
    <div
      className="smart-preview-panel glow-blue-card"
      style={{
        borderColor: `${theme.color}40`,
        boxShadow: `0 0 40px ${theme.glow}, 0 4px 24px rgba(0,0,0,0.4)`,
      }}
    >
      <YtdlpPreviewHeader data={data} subs={subs} setSubs={setSubs} theme={theme} />
      <div className="smart-preview-body">
        <YtdlpEpisodeList
          data={data}
          selectedEpisodes={selectedEpisodes}
          setSelectedEpisodes={setSelectedEpisodes}
          theme={theme}
        />
        {children}
      </div>
    </div>
  );
}
