import { act, renderHook } from "@testing-library/react";
import { useSmartDashboard } from "./useSmartDashboard";

vi.mock("../../lib/api", () => ({
  apiFetch: vi.fn(),
  parseApiError: vi.fn(async (_res: Response, fallback: string) => fallback),
}));

vi.mock("../../context/appStore", () => ({
  useAppStatus: () => ({ voyo_ignore_catalog_drm_hint: false }),
}));

import { apiFetch } from "../../lib/api";

describe("useSmartDashboard voyo DRM", () => {
  beforeEach(() => {
    vi.mocked(apiFetch).mockReset();
  });

  it("blocks smart download when voyo probe is blocking", async () => {
    const showToast = vi.fn();
    const { result } = renderHook(() => useSmartDashboard({ showToast }));

    act(() => {
      result.current.setSmartData({
        service: "voyo",
        mode: "video",
        title: "Widevine naslov",
        target_id: "123",
        drm_blocking: true,
        streamable: false,
        probe_ok: true,
        stream_reason: "Widevine DRM — preuzimanje nije podržano.",
      });
    });

    await act(async () => {
      await result.current.startSmartDownload();
    });

    expect(showToast).toHaveBeenCalledWith(
      "Widevine DRM — preuzimanje nije podržano.",
      "error",
    );
    expect(apiFetch).not.toHaveBeenCalled();
  });
});
