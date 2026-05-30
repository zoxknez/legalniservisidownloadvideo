/** Prefetch lazy tab chunks on sidebar hover for faster tab switches. */
const TAB_PREFETCH: Record<string, () => Promise<unknown>> = {
  dashboard: () => import("../components/tabs/DashboardTab"),
  voyo: () => import("../components/tabs/VoyoTab"),
  hrti: () => import("../components/tabs/HrtiTab"),
  eon: () => import("../components/tabs/EonTab"),
  rts: () => import("../components/tabs/RtsTab"),
  hbo: () => import("../components/tabs/HboTab"),
  iptv: () => import("../components/tabs/IptvTab"),
  drm: () => import("../components/DrmPanel"),
  settings: () => import("../components/tabs/SettingsTab"),
  about: () => import("../components/tabs/AboutTab"),
};

const prefetched = new Set<string>();

export function prefetchTab(tabId: string): void {
  const load = TAB_PREFETCH[tabId];
  if (!load || prefetched.has(tabId)) return;
  prefetched.add(tabId);
  void load();
}
