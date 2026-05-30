import { useAppStatus, useVoyoSlice } from "../../context/appStore";
import type { AppStatus } from "../../types/app";
import type { VoyoSlice } from "./useVoyo";

export function useVoyoTab(): VoyoSlice & { status: AppStatus | null } {
  return { ...useVoyoSlice(), status: useAppStatus() };
}
