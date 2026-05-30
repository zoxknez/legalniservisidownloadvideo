import { renderHook } from "@testing-library/react";
import { useCredentials } from "./useCredentials";
import { wrapperWithStore } from "../../test/renderWithStore";

describe("useCredentials", () => {
  it("merges credential fields from service slices", () => {
    const { result } = renderHook(() => useCredentials(), {
      wrapper: wrapperWithStore({
        voyo: { voyoEmail: "v@test.com", voyoPassword: "v-pass" },
        hrti: { hrtiEmail: "h@test.com" },
        rts: { rtsEmail: "r@test.com" },
        eon: { eonUsername: "eon-user", eonSerial: "ABC123" },
      }),
    });

    expect(result.current.voyoEmail).toBe("v@test.com");
    expect(result.current.voyoPassword).toBe("v-pass");
    expect(result.current.hrtiEmail).toBe("h@test.com");
    expect(result.current.rtsEmail).toBe("r@test.com");
    expect(result.current.eonUsername).toBe("eon-user");
    expect(result.current.eonSerial).toBe("ABC123");
  });
});
