import { useDownloadQueueSlice } from "../../context/appStore";
import type { DownloadQueueSlice } from "./useDownloadQueue";

export function useDownloadQueuePanel(): DownloadQueueSlice {
  return useDownloadQueueSlice();
}
