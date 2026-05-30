import { render, screen, waitFor } from "@testing-library/react";
import { AppProvider } from "./AppProvider";
import { useAppConfigSlice, useSnifferSlice } from "./appStore";
import { mockAppStatus } from "../test/createTestStore";

vi.mock("../hooks/useDownloadWebSocket", () => ({
  useDownloadWebSocket: vi.fn(),
}));

vi.mock("../lib/bridge", () => ({
  fetchUserscriptText: vi.fn().mockResolvedValue("// userscript"),
  USERSCRIPT_INSTALL_URL: "http://test/userscript",
  getUserscriptInstallUrl: () => "http://test/userscript",
}));

vi.mock("../lib/api", () => ({
  apiFetch: vi.fn(),
  getStoredApiKey: () => "",
  parseApiError: async () => "error",
  buildWebSocketUrl: () => "ws://localhost/ws",
}));

import { apiFetch } from "../lib/api";

function BootstrapProbe() {
  const config = useAppConfigSlice();
  const sniffer = useSnifferSlice();

  return (
    <div>
      <span data-testid="output-dir">{config.outputDir}</span>
      <span data-testid="auto-download">{String(sniffer.snifferAutoDownload)}</span>
    </div>
  );
}

describe("AppProvider integration", () => {
  beforeEach(() => {
    vi.mocked(apiFetch).mockReset();
    vi.mocked(apiFetch).mockImplementation(async (url: string) => {
      if (url === "/api/status") {
        return {
          ok: true,
          json: async () => ({
            ...mockAppStatus,
            output_dir: "/bootstrap/out",
            sniffer: { auto_download: false },
          }),
        } as Response;
      }
      if (url === "/api/scheduler/list") {
        return { ok: true, json: async () => [] } as Response;
      }
      if (url === "/api/transcoder/diagnose") {
        return { ok: true, json: async () => ({ ok: true }) } as Response;
      }
      if (url === "/api/sniffer/captures") {
        return {
          ok: true,
          json: async () => ({ captures: [], auto_download: false }),
        } as Response;
      }
      return { ok: false, json: async () => ({}) } as Response;
    });
  });

  it("bootstraps status, scheduler, and syncs sniffer auto-download from status", async () => {
    render(
      <AppProvider>
        <BootstrapProbe />
      </AppProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("output-dir")).toHaveTextContent("/bootstrap/out");
    });

    expect(screen.getByTestId("auto-download")).toHaveTextContent("false");
    expect(apiFetch).toHaveBeenCalledWith("/api/status");
    expect(apiFetch).toHaveBeenCalledWith("/api/scheduler/list");
    expect(apiFetch).toHaveBeenCalledWith("/api/transcoder/diagnose");
  });
});
