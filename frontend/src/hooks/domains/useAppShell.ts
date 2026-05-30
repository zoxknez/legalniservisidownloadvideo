import { useAppShellSlice, useDownloadQueueSlice } from "../../context/appStore";

export function useAppShell() {
  const shell = useAppShellSlice();
  const { downloads, connected } = useDownloadQueueSlice();
  return {
    activeTab: shell.activeTab,
    setActiveTab: shell.setActiveTab,
    toast: shell.toast,
    toastKey: shell.toastKey,
    downloads,
    connected,
  };
}
