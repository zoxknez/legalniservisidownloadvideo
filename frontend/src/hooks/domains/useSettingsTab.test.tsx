import { renderHook } from "@testing-library/react";
import { useSettingsTab } from "./useSettingsTab";
import { mockAppStatus } from "../../test/createTestStore";
import { wrapperWithStore } from "../../test/renderWithStore";

describe("useSettingsTab", () => {
  it("combines config, sniffer, credentials, and shell toast", () => {
    const showToast = vi.fn();
    const saveSnifferAutoDownload = vi.fn();

    const { result } = renderHook(() => useSettingsTab(), {
      wrapper: wrapperWithStore({
        shell: { showToast },
        config: {
          outputDir: "/data/out",
          status: mockAppStatus,
          transcodeMode: "auto",
        },
        sniffer: {
          snifferAutoDownload: false,
          saveSnifferAutoDownload,
          userscriptPreview: "// tampermonkey",
        },
        voyo: { voyoEmail: "settings@voyo.test" },
        eon: { eonUsername: "eon-settings" },
      }),
    });

    expect(result.current.outputDir).toBe("/data/out");
    expect(result.current.status).toEqual(mockAppStatus);
    expect(result.current.transcodeMode).toBe("auto");
    expect(result.current.snifferAutoDownload).toBe(false);
    expect(result.current.userscriptPreview).toBe("// tampermonkey");
    expect(result.current.voyoEmail).toBe("settings@voyo.test");
    expect(result.current.eonUsername).toBe("eon-settings");
    expect(result.current.showToast).toBe(showToast);
    expect(result.current.saveSnifferAutoDownload).toBe(saveSnifferAutoDownload);
  });
});
