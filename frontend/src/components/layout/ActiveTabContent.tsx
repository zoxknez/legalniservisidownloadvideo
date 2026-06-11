import { lazy, Suspense } from "react";

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
const SkyShowtimeTab = lazy(() =>
  import("../tabs/SkyShowtimeTab").then((m) => ({ default: m.SkyShowtimeTab })),
);
const UniversalTab = lazy(() =>
  import("../tabs/UniversalTab").then((m) => ({ default: m.UniversalTab })),
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
    <div className="flex flex-col items-center justify-center min-h-[50vh] gap-4 text-text-secondary">
      <div className="skeleton skeleton-circle" style={{ width: 48, height: 48 }} />
      <div className="flex flex-col gap-2 items-center">
        <div className="skeleton skeleton-text" style={{ width: 120 }} />
        <div className="skeleton skeleton-text-sm" style={{ width: 80 }} />
      </div>
    </div>
  );
}

export function ActiveTabContent({ activeTab }: { activeTab: string }) {
  return (
    <Suspense fallback={<TabLoadingFallback />}>
      <div key={activeTab} className="tab-content-enter">
        {activeTab === "dashboard" && <DashboardTab />}
        {activeTab === "ytdlp" && <UniversalTab />}
        {activeTab === "voyo" && <VoyoTab />}
        {activeTab === "hrti" && <HrtiTab />}
        {activeTab === "eon" && <EonTab />}
        {activeTab === "rts" && <RtsTab />}
        {activeTab === "hbo" && <HboTab />}
        {activeTab === "skyshowtime" && <SkyShowtimeTab />}
        {activeTab === "iptv" && <IptvTab />}
        {activeTab === "drm" && <DrmPanel />}
        {activeTab === "settings" && <SettingsTab />}
        {activeTab === "about" && <AboutTab />}
      </div>
    </Suspense>
  );
}
