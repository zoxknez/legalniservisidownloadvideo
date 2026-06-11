import { describe, expect, it } from "vitest";
import {
  defaultVoyoEpisodeIds,
  voyoCatalogDrmHint,
  voyoIsHardBlocked,
  voyoIsSoftHint,
} from "./voyoDrm";

describe("voyoDrm", () => {
  it("treats catalog drm as hint only when stream is available", () => {
    const item = { drm_hint: true, streamable: true, probe_ok: true, drm_blocking: false };
    expect(voyoCatalogDrmHint(item)).toBe(true);
    expect(voyoIsHardBlocked(item)).toBe(false);
    expect(voyoIsSoftHint(item, false)).toBe(true);
    expect(voyoIsSoftHint(item, true)).toBe(false);
  });

  it("hard blocks on probe widevine", () => {
    const item = { drm_blocking: true, streamable: false, probe_ok: true };
    expect(voyoIsHardBlocked(item)).toBe(true);
    expect(voyoIsSoftHint(item, false)).toBe(false);
  });

  it("default episode selection skips hints unless ignore enabled", () => {
    const eps = [
      { id: 1, drm: false },
      { id: 2, drm: true },
      { id: 3, drm_blocking: true },
    ];
    expect(defaultVoyoEpisodeIds(eps, false)).toEqual([1]);
    expect(defaultVoyoEpisodeIds(eps, true)).toEqual([1, 2]);
  });
});
