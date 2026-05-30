import { lazy, Suspense } from "react";
import { Loader2 } from "lucide-react";

const DashboardTab = lazy(() =>
  import("../tabs/DashboardTab").then((m) => ({ default: m.DashboardTab })),
);
const VoyoTab = lazy(() =>
  import("../tabs/VoyoTab").then((m) => ({ default: m.VoyoTab })),
);
const HrtiTab = lazy(() =>
  import("../tabs/HrtiTab").then((m) => ({ default: m.HrtiTab })),
);
const EonTab = lazy(() =>
  import("../tabs/EonTab").then((m) => ({ default: m.EonTab })),
);
const RtsTab = lazy(() =>
  import("../tabs/RtsTab").then((m) => ({ default: m.RtsTab })),
);
const HboTab = lazy(() =>
  import("../tabs/HboTab").then((m) => ({ default: m.HboTab })),
);
const IptvTab = lazy(() =>
  import("../tabs/IptvTab").then((m) => ({ default: m.IptvTab })),
);
const SettingsTab = lazy(() =>
  import("../tabs/SettingsTab").then((m) => ({ default: m.SettingsTab })),
);
const AboutTab = lazy(() =>
  import("../tabs/AboutTab").then((m) => ({ default: m.AboutTab })),
);
const DrmPanel = lazy(() =>
  import("../DrmPanel").then((m) => ({ default: m.DrmPanel })),
);

function TabLoadingFallback() {
  return (
    <div className="flex flex-col items-center justify-center min-h-[50vh] gap-3 text-text-secondary">
      <Loader2 className="w-8 h-8 animate-spin text-indigo-400" />
      <span className="text-xs font-semibold tracking-wide uppercase">Učitavanje…</span>
    </div>
  );
}

export function ActiveTabContent({ activeTab }: { activeTab: string }) {
  return (
    <Suspense fallback={<TabLoadingFallback />}>
      {activeTab === "dashboard" && <DashboardTab />}
      {activeTab === "voyo" && <VoyoTab />}
      {activeTab === "hrti" && <HrtiTab />}
      {activeTab === "eon" && <EonTab />}
      {activeTab === "rts" && <RtsTab />}
      {activeTab === "hbo" && <HboTab />}
      {activeTab === "iptv" && <IptvTab />}
      {activeTab === "drm" && <DrmPanel />}
      {activeTab === "settings" && <SettingsTab />}
      {activeTab === "about" && <AboutTab />}
    </Suspense>
  );
}
