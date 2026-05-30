import {
  useAppConfigSlice,
  useAppShellSlice,
  useDownloadQueueSlice,
  useEonSlice,
} from "../../context/appStore";
import type { AppStatus } from "../../types/app";
import type { EonSlice } from "./useEon";

export type EonTabSlice = EonSlice & {
  status: AppStatus | null;
  binariesPaths: ReturnType<typeof useAppConfigSlice>["binariesPaths"];
  setBinariesPaths: ReturnType<typeof useAppConfigSlice>["setBinariesPaths"];
  deviceWvdInfo: ReturnType<typeof useAppConfigSlice>["deviceWvdInfo"];
  handleSaveDeviceWvdPath: ReturnType<typeof useAppConfigSlice>["handleSaveDeviceWvdPath"];
  submitLogin: ReturnType<typeof useAppConfigSlice>["submitLogin"];
  fetchScheduledRecordings: ReturnType<typeof useDownloadQueueSlice>["fetchScheduledRecordings"];
  scheduledTasks: ReturnType<typeof useDownloadQueueSlice>["scheduledTasks"];
  showToast: ReturnType<typeof useAppShellSlice>["showToast"];
};

export function useEonTab(): EonTabSlice {
  const eon = useEonSlice();
  const config = useAppConfigSlice();
  const queue = useDownloadQueueSlice();
  const { showToast } = useAppShellSlice();

  return {
    ...eon,
    status: config.status,
    binariesPaths: config.binariesPaths,
    setBinariesPaths: config.setBinariesPaths,
    deviceWvdInfo: config.deviceWvdInfo,
    handleSaveDeviceWvdPath: config.handleSaveDeviceWvdPath,
    submitLogin: config.submitLogin,
    fetchScheduledRecordings: queue.fetchScheduledRecordings,
    scheduledTasks: queue.scheduledTasks,
    showToast,
  };
}
