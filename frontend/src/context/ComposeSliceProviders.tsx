import type { ReactNode } from "react";
import type { AppStore } from "./appStore";
import {
  AppConfigSliceProvider,
  AppShellSliceProvider,
  DownloadQueueSliceProvider,
  EonSliceProvider,
  HboSliceProvider,
  HrtiSliceProvider,
  RtsSliceProvider,
  SmartDashboardSliceProvider,
  SnifferSliceProvider,
  SkyshowtimeSliceProvider,
  VoyoSliceProvider,
} from "./sliceContexts";

export function ComposeSliceProviders({ store, children }: { store: AppStore; children: ReactNode }) {
  return (
    <AppShellSliceProvider value={store.shell}>
      <DownloadQueueSliceProvider value={store.queue}>
        <AppConfigSliceProvider value={store.config}>
          <VoyoSliceProvider value={store.voyo}>
            <HrtiSliceProvider value={store.hrti}>
              <EonSliceProvider value={store.eon}>
                <RtsSliceProvider value={store.rts}>
                  <HboSliceProvider value={store.hbo}>
                    <SkyshowtimeSliceProvider value={store.skyshowtime}>
                      <SmartDashboardSliceProvider value={store.smart}>
                        <SnifferSliceProvider value={store.sniffer}>{children}</SnifferSliceProvider>
                      </SmartDashboardSliceProvider>
                    </SkyshowtimeSliceProvider>
                  </HboSliceProvider>
                </RtsSliceProvider>
              </EonSliceProvider>
            </HrtiSliceProvider>
          </VoyoSliceProvider>
        </AppConfigSliceProvider>
      </DownloadQueueSliceProvider>
    </AppShellSliceProvider>
  );
}
