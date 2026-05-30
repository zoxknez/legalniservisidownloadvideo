import { useAppShellSlice, useAppStatus, useSmartDashboardSlice } from "../../context/appStore";
import type { AppStatus } from "../../types/app";
import type { SmartDashboardSlice } from "./useSmartDashboard";

export function useSmartDashboardTab(): SmartDashboardSlice & {
  status: AppStatus | null;
  showToast: ReturnType<typeof useAppShellSlice>["showToast"];
} {
  const { showToast } = useAppShellSlice();
  return { ...useSmartDashboardSlice(), status: useAppStatus(), showToast };
}
