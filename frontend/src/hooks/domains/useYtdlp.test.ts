import { act, renderHook, waitFor } from "@testing-library/react";
import { useYtdlp } from "./useYtdlp";

vi.mock("../../lib/api", () => ({
  apiFetch: vi.fn(),
  parseApiError: vi.fn(async (res: Response, fallback: string) => {
    try {
      const data = await res.json();
      return (data as { detail?: string }).detail || fallback;
    } catch {
      return fallback;
    }
  }),
}));

import { apiFetch } from "../../lib/api";

describe("useYtdlp", () => {
  beforeEach(() => {
    vi.mocked(apiFetch).mockReset();
  });

  it("calls smart-detect with force=ytdlp", async () => {
    vi.mocked(apiFetch).mockImplementation(async (url) => {
      if (typeof url === "string" && url.includes("/api/smart-detect")) {
        return {
          ok: true,
          json: async () => ({
            service: "ytdlp",
            mode: "video",
            title: "Test video",
            target_id: "https://example.com/video",
            available_resolutions: ["1080p"],
          }),
        } as Response;
      }
      return { ok: true, json: async () => ({ configured: false }) } as Response;
    });

    const showToast = vi.fn();
    const { result } = renderHook(() => useYtdlp({ showToast, activeTab: "ytdlp" }));

    await act(async () => {
      await result.current.analyzeYtdlpUrl("https://example.com/video");
    });

    await waitFor(() => {
      expect(apiFetch).toHaveBeenCalledWith(
        expect.stringContaining("force=ytdlp"),
        expect.any(Object),
      );
    });
    expect(result.current.ytdlpData?.title).toBe("Test video");
  });

  it("starts download via ytdlp API", async () => {
    vi.mocked(apiFetch).mockImplementation(async (url) => {
      if (typeof url === "string" && url.includes("/api/ytdlp/download")) {
        return { ok: true, json: async () => ({ success: true }) } as Response;
      }
      if (typeof url === "string" && url.includes("/api/smart-detect")) {
        return {
          ok: true,
          json: async () => ({
            service: "ytdlp",
            mode: "video",
            title: "Clip",
            target_id: "https://example.com/v",
            available_resolutions: ["1080p"],
          }),
        } as Response;
      }
      return { ok: true, json: async () => ({ configured: false }) } as Response;
    });

    const showToast = vi.fn();
    const { result } = renderHook(() => useYtdlp({ showToast }));

    await act(async () => {
      await result.current.analyzeYtdlpUrl("https://example.com/v");
    });

    await act(async () => {
      await result.current.startYtdlpDownload();
    });

    await waitFor(() => {
      expect(apiFetch).toHaveBeenCalledWith(
        "/api/ytdlp/download",
        expect.objectContaining({ method: "POST" }),
      );
    });

    const downloadCall = vi.mocked(apiFetch).mock.calls.find(
      ([url]) => url === "/api/ytdlp/download",
    );
    const body = JSON.parse(String(downloadCall?.[1]?.body ?? "{}"));
    expect(body.sponsorblock_mode).toBe("disabled");
  });
});
