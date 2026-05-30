import { useSnifferSlice } from "../../context/appStore";
import type { SnifferSlice } from "./useSniffer";

export function useSnifferTab(): SnifferSlice {
  return useSnifferSlice();
}
