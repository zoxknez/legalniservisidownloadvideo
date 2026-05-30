import type { AppShellSlice } from "../context/appStore";
import type { AppConfigSlice } from "../hooks/domains/useAppConfig";
import type { DownloadQueueSlice } from "../hooks/domains/useDownloadQueue";
import type { EonSlice } from "../hooks/domains/useEon";
import type { HboSlice } from "../hooks/domains/useHbo";
import type { HrtiSlice } from "../hooks/domains/useHrti";
import type { RtsSlice } from "../hooks/domains/useRts";
import type { SmartDashboardSlice } from "../hooks/domains/useSmartDashboard";
import type { SnifferSlice } from "../hooks/domains/useSniffer";
import type { VoyoSlice } from "../hooks/domains/useVoyo";

/** Flat view of all app slices — prefer slice hooks for new code. */
export type AppContextValue = AppShellSlice &
  DownloadQueueSlice &
  AppConfigSlice &
  VoyoSlice &
  HrtiSlice &
  EonSlice &
  RtsSlice &
  HboSlice &
  SmartDashboardSlice &
  SnifferSlice;
