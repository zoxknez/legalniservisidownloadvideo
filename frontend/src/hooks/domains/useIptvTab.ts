import { useAppShellSlice, useEonSlice } from "../../context/appStore";

export function useIptvTab() {
  const { eonChannels } = useEonSlice();
  const { showToast } = useAppShellSlice();
  return { eonChannels, showToast };
}
