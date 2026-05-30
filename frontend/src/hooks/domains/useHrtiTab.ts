import { useAppStatus, useHrtiSlice } from "../../context/appStore";
import type { AppStatus } from "../../types/app";
import type { HrtiSlice } from "./useHrti";

export function useHrtiTab(): HrtiSlice & { status: AppStatus | null } {
  return { ...useHrtiSlice(), status: useAppStatus() };
}
