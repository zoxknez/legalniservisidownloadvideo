import { act, renderHook, waitFor } from "@testing-library/react";
import { useAppConfig } from "./useAppConfig";
import { mockAppStatus } from "../../test/createTestStore";

vi.mock("../../lib/api", () => ({
  apiFetch: vi.fn(),
  getStoredApiKey: () => "",
  parseApiError: async () => "error",
}));

import { apiFetch } from "../../lib/api";

describe("useAppConfig", () => {
  beforeEach(() => {
    vi.mocked(apiFetch).mockReset();
  });

  it("notifies subscribeStatusLoaded listeners after fetchStatus", async () => {
    vi.mocked(apiFetch).mockResolvedValue({
      ok: true,
      json: async () => mockAppStatus,
    } as Response);

    const showToast = vi.fn();
    const listener = vi.fn();
    const { result } = renderHook(() => useAppConfig({ showToast }));

    result.current.subscribeStatusLoaded(listener);
    await act(async () => {
      await result.current.fetchStatus();
    });

    await waitFor(() => {
      expect(listener).toHaveBeenCalledWith(mockAppStatus);
      expect(result.current.status).toEqual(mockAppStatus);
    });
    expect(result.current.outputDir).toBe("/tmp/out");
  });

  it("handleClearCredentials returns true when API succeeds", async () => {
    vi.mocked(apiFetch).mockImplementation(async (url: string) => {
      if (url.includes("/api/credentials/clear")) {
        return {
          ok: true,
          json: async () => ({ success: true, message: "ok", service: "voyo" }),
        } as Response;
      }
      if (url.includes("/api/status")) {
        return { ok: true, json: async () => mockAppStatus } as Response;
      }
      return { ok: false, json: async () => ({ detail: "unknown" }) } as Response;
    });

    const showToast = vi.fn();
    const { result } = renderHook(() => useAppConfig({ showToast }));

    let cleared = false;
    await act(async () => {
      cleared = await result.current.handleClearCredentials("voyo");
    });

    expect(cleared).toBe(true);
    expect(showToast).toHaveBeenCalledWith("ok", "success");
  });

  it("handleClearCredentials returns false when API fails", async () => {
    vi.mocked(apiFetch).mockResolvedValue({
      ok: false,
      json: async () => ({ detail: "fail" }),
    } as Response);

    const showToast = vi.fn();
    const { result } = renderHook(() => useAppConfig({ showToast }));

    let cleared = false;
    await act(async () => {
      cleared = await result.current.handleClearCredentials("voyo");
    });

    expect(cleared).toBe(false);
  });

  it("unsubscribes status listeners on cleanup", async () => {
    vi.mocked(apiFetch).mockResolvedValue({
      ok: true,
      json: async () => mockAppStatus,
    } as Response);

    const showToast = vi.fn();
    const listener = vi.fn();
    const { result } = renderHook(() => useAppConfig({ showToast }));

    const unsubscribe = result.current.subscribeStatusLoaded(listener);
    unsubscribe();

    await act(async () => {
      await result.current.fetchStatus();
    });
    expect(listener).not.toHaveBeenCalled();
  });
});
