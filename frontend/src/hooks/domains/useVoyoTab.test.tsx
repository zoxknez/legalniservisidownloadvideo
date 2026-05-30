import { renderHook } from "@testing-library/react";
import { useVoyoTab } from "./useVoyoTab";
import { mockAppStatus } from "../../test/createTestStore";
import { wrapperWithStore } from "../../test/renderWithStore";

describe("useVoyoTab", () => {
  it("exposes voyo slice fields and app status", () => {
    const { result } = renderHook(() => useVoyoTab(), {
      wrapper: wrapperWithStore({
        voyo: { voyoEmail: "tab@voyo.test", voyoRes: "720p" },
        config: { status: mockAppStatus },
      }),
    });

    expect(result.current.voyoEmail).toBe("tab@voyo.test");
    expect(result.current.voyoRes).toBe("720p");
    expect(result.current.status).toEqual(mockAppStatus);
  });
});
