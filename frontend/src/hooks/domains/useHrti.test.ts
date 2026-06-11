import { describe, expect, it } from "vitest";
import { extractHrtiRefId } from "./useHrti";

describe("extractHrtiRefId", () => {
  it("extracts uuid from vod url", () => {
    const id = "9a7bb881-0b1b-bc57-ab38-07b93d293a56";
    expect(extractHrtiRefId(`https://hrti.hrt.hr/video/vod/${id}/slatka-simona`)).toBe(id);
  });

  it("accepts bare reference id", () => {
    expect(extractHrtiRefId("domaći_filmovi")).toBe("domaći_filmovi");
    expect(extractHrtiRefId("  abc-123  ")).toBe("abc-123");
  });

  it("returns null for empty input", () => {
    expect(extractHrtiRefId("")).toBeNull();
    expect(extractHrtiRefId("   ")).toBeNull();
  });
});
