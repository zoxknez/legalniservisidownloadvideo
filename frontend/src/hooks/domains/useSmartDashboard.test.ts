import { act, renderHook, waitFor } from "@testing-library/react";
import { useSmartDashboard } from "./useSmartDashboard";

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

describe("useSmartDashboard", () => {
  beforeEach(() => {
    vi.mocked(apiFetch).mockReset();
  });

  it("sends ytdlp download with video_title and playlist items", async () => {
    vi.mocked(apiFetch).mockImplementation(async (url, init) => {
      if (typeof url === "string" && url.includes("/api/ytdlp/download")) {
        return { ok: true, json: async () => ({ success: true, task_id: "t1" }) } as Response;
      }
      return { ok: true, json: async () => ({ configured: false }) } as Response;
    });

    const showToast = vi.fn();
    const { result } = renderHook(() => useSmartDashboard({ showToast }));

    act(() => {
      result.current.setSmartData({
        service: "ytdlp",
        mode: "playlist",
        title: "Test plejlista",
        target_id: "https://www.youtube.com/playlist?list=PLtest",
        episodes: [
          { id: "1", title: "Prvi", episode: 1 },
          { id: "2", title: "Drugi", episode: 2 },
        ],
      });
      result.current.setSmartSelectedEpisodes(["1"]);
      result.current.setSmartResolution("720p");
      result.current.setSmartSubs("en");
    });

    await act(async () => {
      await result.current.startSmartDownload();
    });

    await waitFor(() => {
      expect(apiFetch).toHaveBeenCalledWith(
        "/api/ytdlp/download",
        expect.objectContaining({
          method: "POST",
          body: expect.stringContaining('"video_title":"Test plejlista"'),
        }),
      );
    });

    const body = JSON.parse(
      (vi.mocked(apiFetch).mock.calls.find((c) => String(c[0]).includes("download"))?.[1] as { body: string }).body,
    );
    expect(body.download_playlist).toBe(true);
    expect(body.playlist_items).toBe("1");
  });

  it("shows toast when smart detect fails", async () => {
    vi.mocked(apiFetch).mockResolvedValue({
      ok: false,
      json: async () => ({ detail: "Nepoznat URL" }),
    } as Response);

    const showToast = vi.fn();
    const { result } = renderHook(() => useSmartDashboard({ showToast }));

    await act(async () => {
      await result.current.handleSmartDetect("https://example.com/video");
    });

    expect(showToast).toHaveBeenCalledWith("Nepoznat URL", "error");
  });
});
