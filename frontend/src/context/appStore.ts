import type { Dispatch, SetStateAction } from "react";
import type { ShowToastFn } from "../hooks/domainTypes";
import type { AppConfigSlice } from "../hooks/domains/useAppConfig";
import type { DownloadQueueSlice } from "../hooks/domains/useDownloadQueue";
import type { EonSlice } from "../hooks/domains/useEon";
import type { HboSlice } from "../hooks/domains/useHbo";
import type { HrtiSlice } from "../hooks/domains/useHrti";
import type { RtsSlice } from "../hooks/domains/useRts";
import type { SmartDashboardSlice } from "../hooks/domains/useSmartDashboard";
import type { SnifferSlice } from "../hooks/domains/useSniffer";
import type { VoyoSlice } from "../hooks/domains/useVoyo";
import type { SkyshowtimeSlice } from "../hooks/domains/useSkyshowtime";
import type { YtdlpSlice } from "../hooks/domains/useYtdlp";
import type { AppStatus, ToastType } from "../types/app";

export interface AppShellSlice {
  activeTab: string;
  setActiveTab: (tab: string) => void;
  toast: { message: string; type: ToastType } | null;
  toastKey: number;
  setToast: Dispatch<SetStateAction<{ message: string; type: ToastType } | null>>;
  setToastKey: Dispatch<SetStateAction<number>>;
  showToast: ShowToastFn;
}

export interface AppStore {
  shell: AppShellSlice;
  queue: DownloadQueueSlice;
  config: AppConfigSlice;
  voyo: VoyoSlice;
  hrti: HrtiSlice;
  eon: EonSlice;
  rts: RtsSlice;
  hbo: HboSlice;
  smart: SmartDashboardSlice;
  sniffer: SnifferSlice;
  skyshowtime: SkyshowtimeSlice;
  ytdlp: YtdlpSlice;
}

export {
  useAppShellSlice,
  useDownloadQueueSlice,
  useAppConfigSlice,
  useVoyoSlice,
  useHrtiSlice,
  useEonSlice,
  useRtsSlice,
  useHboSlice,
  useSmartDashboardSlice,
  useSnifferSlice,
  useSkyshowtimeSlice,
  useYtdlpSlice,
} from "./sliceContexts";

import { useAppConfigSlice } from "./sliceContexts";

export function useAppStatus(): AppStatus | null {
  return useAppConfigSlice().status;
}

export function flattenAppStore(store: AppStore) {
  return {
    ...store.shell,
    ...store.queue,
    ...store.config,
    ...store.voyo,
    ...store.hrti,
    ...store.eon,
    ...store.rts,
    ...store.hbo,
    ...store.smart,
    ...store.sniffer,
    ...store.skyshowtime,
    ...store.ytdlp,
  };
}
