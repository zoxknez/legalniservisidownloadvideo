import { useAppStatus, useHboSlice } from "../../context/appStore";
import type { AppStatus } from "../../types/app";
import type { HboSlice } from "./useHbo";

export function useHboTab(): HboSlice & { status: AppStatus | null } {
  return { ...useHboSlice(), status: useAppStatus() };
}
