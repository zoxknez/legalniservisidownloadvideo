import { act, renderHook } from "@testing-library/react";
import { useVoyo } from "./useVoyo";

vi.mock("../../lib/api", () => ({
  apiFetch: vi.fn(),
  parseApiError: vi.fn(async (_res: Response, fallback: string) => fallback),
}));

vi.mock("../../context/appStore", () => ({
  useAppStatus: () => ({ voyo_ignore_catalog_drm_hint: false }),
}));

import { apiFetch } from "../../lib/api";

describe("useVoyo", () => {
  beforeEach(() => {
    vi.mocked(apiFetch).mockReset();
  });

  it("blocks download when probe says stream is unavailable", async () => {
    vi.mocked(apiFetch).mockResolvedValue({
      ok: true,
      json: async () => ({ success: true, task_id: "t1" }),
    } as Response);

    const showToast = vi.fn();
    const { result } = renderHook(() => useVoyo({ showToast }));

    act(() => {
      result.current.setVoyoMode("video");
      result.current.setVoyoTarget("12345");
      result.current.setVoyoVideoPreview({
        title: "Widevine naslov",
        drm_hint: true,
        drm_blocking: true,
        streamable: false,
        probe_ok: true,
        stream_reason: "Widevine DRM — preuzimanje nije podržano.",
      });
    });

    await act(async () => {
      await result.current.startVoyoDownload();
    });

    expect(showToast).toHaveBeenCalledWith(
      "Widevine DRM — preuzimanje nije podržano.",
      "error",
    );
    expect(apiFetch).not.toHaveBeenCalled();
  });
});
