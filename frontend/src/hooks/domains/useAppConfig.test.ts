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
