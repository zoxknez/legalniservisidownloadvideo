import { AppProvider } from "./context/AppProvider";
import { useAppShell } from "./hooks/domains/useAppShell";
import { AppSidebar } from "./components/layout/AppSidebar";
import { AppToast } from "./components/layout/AppToast";
import { SnifferToast } from "./components/layout/SnifferToast";
import { DownloadQueuePanel } from "./components/layout/DownloadQueuePanel";
import { LogModal } from "./components/layout/LogModal";
import { HrtiDownloadModal } from "./components/layout/HrtiDownloadModal";
import { ActiveTabContent } from "./components/layout/ActiveTabContent";

function AppLayout() {
  const { activeTab } = useAppShell();

  return (
    <div className="flex w-full min-h-screen">
      <AppToast />
      <SnifferToast />
      <AppSidebar />

      <main className="flex-1 p-10 overflow-y-auto max-h-screen">
        <ActiveTabContent activeTab={activeTab} />
      </main>

      <DownloadQueuePanel />
      <LogModal />
      <HrtiDownloadModal />
    </div>
  );
}

export default function App() {
  return (
    <AppProvider>
      <AppLayout />
    </AppProvider>
  );
}
