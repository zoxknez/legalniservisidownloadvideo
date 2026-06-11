import { useAppShellSlice, useAppStatus, useYtdlpSlice } from "../../context/appStore";
import type { AppStatus } from "../../types/app";
import type { YtdlpSlice } from "./useYtdlp";

export function useYtdlpTab(): YtdlpSlice & {
  status: AppStatus | null;
  activeTab: string;
} {
  const { activeTab } = useAppShellSlice();
  return { ...useYtdlpSlice(), status: useAppStatus(), activeTab };
}
