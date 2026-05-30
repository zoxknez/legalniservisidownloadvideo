import { act, renderHook, waitFor } from "@testing-library/react";
import { useVoyo } from "./useVoyo";

vi.mock("../../lib/api", () => ({
  apiFetch: vi.fn(),
}));

import { apiFetch } from "../../lib/api";

describe("useVoyo", () => {
  beforeEach(() => {
    vi.mocked(apiFetch).mockReset();
  });

  it("loads series data when search succeeds", async () => {
    const series = {
      id: 42,
      title: "Test Series",
      episodes: [{ id: 1, title: "Ep 1", number: 1 }],
    };

    vi.mocked(apiFetch).mockResolvedValue({
      ok: true,
      json: async () => series,
    } as Response);

    const showToast = vi.fn();
    const { result } = renderHook(() => useVoyo({ showToast }));

    act(() => {
      result.current.setVoyoTarget("12345");
    });

    await act(async () => {
      await result.current.searchVoyoSeries();
    });

    await waitFor(() => {
      expect(result.current.voyoSeriesData).toEqual(series);
    });
    expect(result.current.selectedVoyoEpisodes).toEqual([1]);
    expect(apiFetch).toHaveBeenCalledWith("/api/voyo/series/12345");
  });

  it("shows toast when search fails", async () => {
    vi.mocked(apiFetch).mockResolvedValue({
      ok: false,
      json: async () => ({ detail: "Series not found" }),
    } as Response);

    const showToast = vi.fn();
    const { result } = renderHook(() => useVoyo({ showToast }));

    act(() => {
      result.current.setVoyoTarget("999");
    });

    await act(async () => {
      await result.current.searchVoyoSeries();
    });

    expect(showToast).toHaveBeenCalledWith("Series not found", "error");
    expect(result.current.voyoSeriesData).toBeNull();
  });
});
