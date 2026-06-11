import { describe, expect, it } from "vitest";
import { buildYtdlpCtaLabel, toggleYtdlpSubsLang } from "./ytdlpShared";

describe("ytdlpShared", () => {
  it("toggles subtitle languages", () => {
    expect(toggleYtdlpSubsLang("sr,en", "hr")).toBe("sr,en,hr");
    expect(toggleYtdlpSubsLang("sr,en,hr", "en")).toBe("sr,hr");
    expect(toggleYtdlpSubsLang("", "sr")).toBe("sr");
  });

  it("builds dynamic CTA labels", () => {
    expect(buildYtdlpCtaLabel({ submitting: true })).toBe("Dodavanje u red...");
    expect(buildYtdlpCtaLabel({ submitting: false, mode: "video" })).toBe(
      "Dodaj u red preuzimanja",
    );
    expect(
      buildYtdlpCtaLabel({
        submitting: false,
        mode: "playlist",
        selectedCount: 3,
        totalEpisodes: 10,
      }),
    ).toBe("Preuzmi 3 od 10 stavke");
    expect(
      buildYtdlpCtaLabel({
        submitting: false,
        mode: "playlist",
        selectedCount: 10,
        totalEpisodes: 10,
      }),
    ).toBe("Preuzmi celu plejlistu (10 stavki)");
  });
});
