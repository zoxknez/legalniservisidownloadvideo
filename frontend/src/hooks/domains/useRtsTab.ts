import { useAppStatus, useRtsSlice } from "../../context/appStore";
import type { AppStatus } from "../../types/app";
import type { RtsSlice } from "./useRts";

export function useRtsTab(): RtsSlice & { status: AppStatus | null } {
  return { ...useRtsSlice(), status: useAppStatus() };
}
