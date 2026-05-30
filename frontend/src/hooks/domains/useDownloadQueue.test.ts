import { act, renderHook, waitFor } from "@testing-library/react";
import { useDownloadQueue } from "./useDownloadQueue";
import type { DownloadTask } from "../../types/app";

vi.mock("../../lib/api", () => ({
  apiFetch: vi.fn(),
}));

import { apiFetch } from "../../lib/api";

const sampleDownloads: DownloadTask[] = [
  {
    id: "1",
    service: "voyo",
    title: "Active",
    status: "downloading",
    progress: 50,
    speed: "1.2 MB/s",
    eta: "01:00",
    logs: [],
  },
  {
    id: "2",
    service: "hrti",
    title: "Done",
    status: "finished",
    progress: 100,
    speed: "",
    eta: "",
    logs: [],
  },
  {
    id: "3",
    service: "eon",
    title: "Queued",
    status: "pending",
    progress: 0,
    speed: "",
    eta: "",
    logs: [],
  },
];

describe("useDownloadQueue", () => {
  beforeEach(() => {
    vi.mocked(apiFetch).mockReset();
  });

  it("counts active downloads as downloading or pending tasks", () => {
    const showToast = vi.fn();
    const { result } = renderHook(() => useDownloadQueue({ showToast }));

    act(() => {
      result.current.setDownloads(sampleDownloads);
    });

    expect(result.current.activeDownloadsCount).toBe(2);
  });

  it("loads scheduled recordings from the scheduler API", async () => {
    const scheduled = [{
      id: "s1",
      title: "Recording",
      channel_name: "HRT 1",
      duration: 3600,
      start_time: "2026-01-01T00:00:00Z",
    }];
    vi.mocked(apiFetch).mockResolvedValue({
      ok: true,
      json: async () => scheduled,
    } as Response);

    const showToast = vi.fn();
    const { result } = renderHook(() => useDownloadQueue({ showToast }));

    await act(async () => {
      await result.current.fetchScheduledRecordings();
    });

    await waitFor(() => {
      expect(result.current.scheduledTasks).toEqual(scheduled);
    });
    expect(apiFetch).toHaveBeenCalledWith("/api/scheduler/list");
  });

  it("shows info toast when cancel is requested", async () => {
    vi.mocked(apiFetch).mockResolvedValue({ ok: true } as Response);
    const showToast = vi.fn();
    const { result } = renderHook(() => useDownloadQueue({ showToast }));

    await act(async () => {
      await result.current.cancelDownloadTask("task-42");
    });

    expect(apiFetch).toHaveBeenCalledWith("/api/queue/cancel", expect.objectContaining({
      method: "POST",
      body: JSON.stringify({ id: "task-42" }),
    }));
    expect(showToast).toHaveBeenCalledWith("Slanje zahteva za otkazivanje...", "info");
  });

  it("shows success toast when retry succeeds", async () => {
    vi.mocked(apiFetch).mockResolvedValue({ ok: true, json: async () => ({}) } as Response);
    const showToast = vi.fn();
    const { result } = renderHook(() => useDownloadQueue({ showToast }));

    await act(async () => {
      await result.current.retryDownloadTask("task-99");
    });

    expect(showToast).toHaveBeenCalledWith("Preuzimanje ponovo pokrenuto!", "success");
  });

  it("clears completed queue and resets confirm dialog", async () => {
    vi.mocked(apiFetch).mockResolvedValue({ ok: true } as Response);
    const showToast = vi.fn();
    const { result } = renderHook(() => useDownloadQueue({ showToast }));

    act(() => {
      result.current.setConfirmClear(true);
    });

    await act(async () => {
      await result.current.clearCompletedQueue();
    });

    expect(result.current.confirmClear).toBe(false);
    expect(showToast).toHaveBeenCalledWith("Očišćen red preuzimanja!");
  });
});
