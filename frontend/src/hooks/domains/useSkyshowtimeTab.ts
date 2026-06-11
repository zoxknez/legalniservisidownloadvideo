import { useAppStatus, useSkyshowtimeSlice } from "../../context/appStore";
import type { AppStatus } from "../../types/app";
import type { SkyshowtimeSlice } from "./useSkyshowtime";

export function useSkyshowtimeTab(): SkyshowtimeSlice & { status: AppStatus | null } {
  return { ...useSkyshowtimeSlice(), status: useAppStatus() };
}
